"""gau-status — batch status check for Gaussian log files."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from gautools.parsers.log import get_log_status


def _format_imag(freqs: list[float]) -> str:
    if not freqs:
        return "—"
    parts = [f"{f:.1f}" for f in freqs]
    return f"{len(freqs)}  ({', '.join(parts)} cm⁻¹)"


def _status_label(normal: bool, n_atoms: int) -> str:
    if n_atoms == 0:
        return "Error"
    if normal:
        return "Normal"
    return "Incomplete"


@click.command("gau-status")
@click.argument("targets", nargs=-1, type=click.Path(path_type=Path))
@click.option("--ext", default="log", show_default=True,
              help="File extension to scan when a directory is given.")
@click.option("--sort", type=click.Choice(["name", "status"]), default="name",
              show_default=True, help="Sort order.")
@click.option("--csv", "as_csv", is_flag=True, default=False,
              help="Output as CSV instead of a formatted table.")
def main(
    targets: tuple[Path, ...],
    ext: str,
    sort: str,
    as_csv: bool,
) -> None:
    """Report status, atom count, and imaginary frequencies for log files.

    TARGETS can be log files or directories (which are scanned for *.log files).
    Defaults to scanning the current directory if no targets are given.
    """
    log_paths: list[Path] = []
    if not targets:
        targets = (Path.cwd(),)

    for t in targets:
        t = Path(t)
        if t.is_dir():
            log_paths.extend(sorted(t.glob(f"*.{ext}")))
        elif t.exists():
            log_paths.append(t)
        else:
            click.echo(f"Warning: {t} not found", err=True)

    if not log_paths:
        click.echo("No log files found.")
        return

    # Gather data
    rows: list[tuple[str, str, str, str]] = []  # file, status, atoms, imag
    any_error = False

    for p in log_paths:
        try:
            st = get_log_status(p)
        except Exception as e:
            rows.append((p.name, "Error", "—", "—"))
            any_error = True
            continue

        status = _status_label(st.normal_termination, st.n_atoms)
        if status != "Normal":
            any_error = True

        atoms_str = str(st.n_atoms) if st.n_atoms else "—"
        imag_str  = _format_imag(st.imaginary_frequencies) if st.has_freq else "—"
        rows.append((p.name, status, atoms_str, imag_str))

    # Sort
    if sort == "status":
        order = {"Error": 0, "Incomplete": 1, "Normal": 2}
        rows.sort(key=lambda r: (order.get(r[1], 9), r[0]))
    else:
        rows.sort(key=lambda r: r[0])

    # Output
    headers = ("File", "Status", "Atoms", "Imaginary Freqs")

    if as_csv:
        click.echo(",".join(headers))
        for row in rows:
            click.echo(",".join(row))
    else:
        widths = [
            max(len(h), max(len(r[i]) for r in rows))
            for i, h in enumerate(headers)
        ]
        fmt = "  ".join(f"{{:<{w}}}" for w in widths)
        sep = "  ".join("-" * w for w in widths)
        click.echo(fmt.format(*headers))
        click.echo(sep)
        for row in rows:
            click.echo(fmt.format(*row))

    sys.exit(1 if any_error else 0)
