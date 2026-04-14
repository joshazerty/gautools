"""scan2qst2 — analyse a relaxed scan and optionally generate a QST2 input."""

from __future__ import annotations

import re
from pathlib import Path

import click

from gautools._console import log_error, log_header, log_info, log_success, log_warn
from gautools.parsers.inp import find_input_file, parse_gaussian_input, write_gaussian_file, GaussianInput
from gautools.route import route_for_qst2


def _require_scan_deps() -> tuple:
    """Lazy import of cclib/numpy/matplotlib with a helpful error if missing."""
    try:
        import cclib
        import numpy as np
        import matplotlib.pyplot as plt
        return cclib, np, plt
    except ImportError as e:
        raise click.ClickException(
            f"scan2qst2 requires additional dependencies: {e}\n"
            "Install them with:  pip install gautools[scan]"
        )


def _parse_scan_atoms(inp_file: Path) -> tuple[list[int], str]:
    """Return (0-based atom indices, scan_type) from a scan input file."""
    text = inp_file.read_text(errors="replace")
    regex = re.compile(r"^\s*(?:[a-zA-Z]\s+)?((?:\d+\s+){2,4})[Ss]\s+\d+", re.MULTILINE)
    for match in reversed(list(regex.finditer(text))):
        indices = [int(x) - 1 for x in match.group(1).split()]
        n = len(indices)
        scan_type = {2: "Bond", 3: "Angle", 4: "Dihedral"}.get(n, "Unknown")
        return indices, scan_type
    return [], "Unknown"


def _calc_coordinate(geom, indices: list[int], scan_type: str) -> float:
    import numpy as np
    pts = [np.array(geom[i]) for i in indices]
    if scan_type == "Bond":
        return float(np.linalg.norm(pts[0] - pts[1]))
    elif scan_type == "Angle":
        v1, v2 = pts[0] - pts[1], pts[2] - pts[1]
        cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    elif scan_type == "Dihedral":
        b1 = -1.0 * (pts[1] - pts[0])
        b2 = pts[2] - pts[1]
        b3 = pts[3] - pts[2]
        b2n = b2 / np.linalg.norm(b2)
        v = b1 - np.dot(b1, b2n) * b2n
        w = b3 - np.dot(b3, b2n) * b2n
        return float(np.degrees(np.arctan2(np.dot(np.cross(b2n, v), w), np.dot(v, w))))
    return 0.0


def _plot_pes(x, y, scan_type: str) -> int:
    """Plot PES, return index of maximum."""
    _, np, plt = _require_scan_deps()
    max_idx = int(np.argmax(y))

    xlabel = (
        r"Bond Length ($\AA$)" if scan_type == "Bond"
        else f"{scan_type} (degrees)" if scan_type in ("Angle", "Dihedral")
        else "Scan Step"
    )
    plt.rcParams.update({"font.size": 12, "font.family": "sans-serif"})
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(x, y, "o-", color="#003366", lw=2, markersize=8, mfc="#4d79ff", mec="#003366")
    ax.plot(x[max_idx], y[max_idx], "*", color="#cc0000", ms=20, zorder=5)
    ax.set_xlabel(xlabel, fontsize=14, fontweight="bold")
    ax.set_ylabel(r"Relative Energy (kcal mol$^{-1}$)", fontsize=14, fontweight="bold")
    ax.set_title(f"Relaxed Scan Profile ({scan_type})", fontsize=16, pad=15)
    y_off = (max(y) - min(y)) * 0.1 or 1.0
    ax.annotate(
        f"TS Estimate\n{x[max_idx]:.3f} / {y[max_idx]:.1f} kcal/mol",
        xy=(x[max_idx], y[max_idx]),
        xytext=(x[max_idx], y[max_idx] + y_off),
        arrowprops=dict(facecolor="#cc0000", shrink=0.05, width=2, headwidth=8),
        fontsize=10, ha="center",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cc0000", alpha=0.9),
    )
    ax.grid(True, ls="--", alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.show()
    return max_idx


@click.command("scan2qst2")
@click.argument("logfile", type=click.Path(exists=True, path_type=Path))
@click.option("--inp", "inp_file", type=click.Path(exists=True, path_type=Path),
              default=None, help="Gaussian input file (auto-detected if omitted).")
@click.option("--no-plot", is_flag=True, default=False,
              help="Skip the interactive PES plot (useful on headless nodes).")
@click.option("--qst2/--no-qst2", default=None,
              help="Generate QST2 input without prompting.")
@click.option("--output", "output_file", type=click.Path(path_type=Path),
              default=None, help="Output filename [default: <stem>_qst2.gjf].")
def main(
    logfile: Path,
    inp_file: Path | None,
    no_plot: bool,
    qst2: bool | None,
    output_file: Path | None,
) -> None:
    """Analyse a relaxed scan PES and optionally generate a QST2 input."""
    cclib, np, plt = _require_scan_deps()
    log_header("scan2qst2 — Scan Analyser")
    log_info(f"Log file: {logfile}")

    # Parse with cclib
    try:
        data = cclib.io.ccread(str(logfile))
    except Exception as e:
        log_error(f"cclib failed: {e}")
        raise SystemExit(1)

    if hasattr(data, "optstatus") and len(data.optstatus) > 0:
        valid = [i for i, s in enumerate(data.optstatus) if s & cclib.parser.data.ccData.OPT_DONE]
        if not valid:
            log_warn("No converged scan points found — using all geometries")
            valid = list(range(len(data.scfenergies)))
    else:
        valid = list(range(len(data.scfenergies)))

    energies_ev = data.scfenergies[valid]
    coords      = data.atomcoords[valid]
    atom_nos    = data.atomnos
    log_success(f"Found {len(valid)} converged scan points")

    energies_kcal = (energies_ev - np.min(energies_ev)) * 23.0605

    # Get scan coordinate
    resolved_inp = inp_file or find_input_file(logfile)
    if resolved_inp:
        scan_atoms, scan_type = _parse_scan_atoms(resolved_inp)
        log_success(f"Detected {scan_type} scan on atoms: {scan_atoms}")
    else:
        scan_atoms, scan_type = [], "Unknown"
        log_warn("No input file found — using step number as x-axis")

    x_vals = np.array(
        [_calc_coordinate(c, scan_atoms, scan_type) for c in coords]
        if scan_atoms else list(range(len(energies_kcal)))
    )

    # Plot
    if no_plot:
        max_idx = int(np.argmax(energies_kcal))
        log_info(f"Scan maximum at step {max_idx} (x={x_vals[max_idx]:.3f}, "
                 f"E={energies_kcal[max_idx]:.2f} kcal/mol)")
    else:
        max_idx = _plot_pes(x_vals, energies_kcal, scan_type)

    # QST2 generation
    if max_idx == 0 or max_idx == len(coords) - 1:
        log_warn("Maximum is at the edge of the scan — extend your scan range before using QST2")
        return

    if qst2 is None and not no_plot:
        qst2 = click.confirm("Generate QST2 input file?", default=True)
    elif qst2 is None:
        qst2 = True

    if not qst2:
        return

    if resolved_inp is None:
        log_error("Cannot generate QST2: no input file found.")
        raise SystemExit(1)

    template = parse_gaussian_input(resolved_inp)
    new_route = route_for_qst2(template.route)

    out_path = output_file or (logfile.parent / f"{logfile.stem}_qst2.gjf")

    from gautools._constants import get_symbol
    # Build geometry lines for reactant (max_idx-1) and product (max_idx+1)
    def _geom_atoms(frame_coords):
        from gautools.parsers.log import Atom
        return [Atom(symbol=get_symbol(z), x=c[0], y=c[1], z=c[2])
                for z, c in zip(atom_nos, frame_coords)]

    reactant = _geom_atoms(coords[max_idx - 1])
    product  = _geom_atoms(coords[max_idx + 1])

    # Remove scan lines from footer
    clean_footer = [
        l for l in template.footer
        if not re.search(r"^\s*((?:\d+\s+)+)[Ss]\s+\d+", l)
    ]

    # Write QST2: reactant block + product block (separated by blank line)
    out_inp = GaussianInput(
        link0=template.link0,
        route=new_route,
        title=template.title or ["QST2 guess"],
        charge_mult=template.charge_mult,
        atoms=reactant,
        footer=[],
    )
    # We need to append the product block manually
    lines: list[str] = []
    link0 = [l for l in template.link0 if not l.lower().startswith("%chk")]
    link0.insert(0, f"%chk={out_path.stem}.chk")
    for l in link0:
        lines.append(l)
    lines.append(new_route)
    lines.append("")
    for t in (template.title or ["QST2 guess"]):
        lines.append(t)
    lines.append("")
    lines.append(template.charge_mult)
    for a in reactant:
        lines.append(a.format())
    lines.append("")
    for a in product:
        lines.append(a.format())
    lines.append("")
    for l in clean_footer:
        lines.append(l)
    if lines and lines[-1].strip():
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n")

    log_success(f"QST2 input written: {out_path}")
    log_header("Done")
