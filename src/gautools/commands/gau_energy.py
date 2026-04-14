"""gau-energy — extract and compare thermochemical energies from log files."""

from __future__ import annotations

from pathlib import Path

import click

from gautools.parsers.log import parse_energies, parse_termination


_HARTREE_TO_KCAL = 627.5094740631
_HARTREE_TO_KJ   = 2625.4996394799


def _rel(val: float | None, ref: float | None, factor: float) -> str:
    if val is None or ref is None:
        return "—"
    delta = (val - ref) * factor
    return f"{delta:+.2f}"


def _fmt(val: float | None, prec: int = 6) -> str:
    if val is None:
        return "—"
    return f"{val:.{prec}f}"


@click.command("gau-energy")
@click.argument("logfiles", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--ref", "ref_file", type=click.Path(exists=True, path_type=Path),
              default=None,
              help="Reference file for ΔE columns (default: lowest G among inputs).")
@click.option("--unit", type=click.Choice(["kcal", "kj", "hartree"]), default="kcal",
              show_default=True, help="Unit for relative energy columns.")
@click.option("--csv", "as_csv", is_flag=True, default=False,
              help="Output as CSV.")
@click.option("--sort", type=click.Choice(["name", "g", "h", "scf"]), default="name",
              show_default=True, help="Sort rows by this column.")
def main(
    logfiles: tuple[Path, ...],
    ref_file: Path | None,
    unit: str,
    as_csv: bool,
    sort: str,
) -> None:
    """Extract and compare thermochemical energies from Gaussian log files.

    Outputs SCF, ZPE, E+ZPE, enthalpy, and Gibbs free energy, with relative
    values (ΔG, ΔH) referenced to the chosen file or the lowest-G structure.
    """
    factor = {
        "kcal":    _HARTREE_TO_KCAL,
        "kj":      _HARTREE_TO_KJ,
        "hartree": 1.0,
    }[unit]
    unit_label = {"kcal": "kcal/mol", "kj": "kJ/mol", "hartree": "Ha"}[unit]

    # Gather energies
    data: list[tuple[Path, object, bool]] = []
    for p in logfiles:
        e = parse_energies(p)
        ok = parse_termination(p)
        data.append((p, e, ok))

    # Determine reference
    ref_g: float | None = None
    if ref_file is not None:
        ref_e = parse_energies(ref_file)
        ref_g = ref_e.gibbs
    else:
        # lowest Gibbs
        gibbsvals = [e.gibbs for _, e, _ in data if e.gibbs is not None]
        ref_g = min(gibbsvals) if gibbsvals else None

    ref_h = None
    if ref_file is not None:
        ref_h = parse_energies(ref_file).enthalpy
    else:
        hvals = [e.enthalpy for _, e, _ in data if e.enthalpy is not None]
        ref_h = min(hvals) if hvals else None

    # Sort
    sort_key = {
        "name": lambda t: t[0].name,
        "g":    lambda t: (t[1].gibbs    is None, t[1].gibbs    or 0),
        "h":    lambda t: (t[1].enthalpy is None, t[1].enthalpy or 0),
        "scf":  lambda t: (t[1].scf_hartree is None, t[1].scf_hartree or 0),
    }[sort]
    data.sort(key=sort_key)

    # Build table
    headers = [
        "File", "OK",
        "SCF (Ha)", "ZPE (Ha)", "E+ZPE (Ha)", "H (Ha)", "G (Ha)",
        f"ΔH ({unit_label})", f"ΔG ({unit_label})",
    ]
    rows: list[list[str]] = []
    for p, e, ok in data:
        rows.append([
            p.name,
            "✔" if ok else "✘",
            _fmt(e.scf_hartree),
            _fmt(e.zpe_hartree),
            _fmt(e.e_zpe),
            _fmt(e.enthalpy),
            _fmt(e.gibbs),
            _rel(e.enthalpy, ref_h, factor),
            _rel(e.gibbs,    ref_g, factor),
        ])

    if as_csv:
        click.echo(",".join(headers))
        for row in rows:
            click.echo(",".join(row))
        return

    widths = [
        max(len(h), max((len(r[i]) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  ".join("-" * w for w in widths)
    click.echo(fmt.format(*headers))
    click.echo(sep)
    for row in rows:
        click.echo(fmt.format(*row))
