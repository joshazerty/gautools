"""gau2xyz — extract geometry from Gaussian log file(s) to XYZ."""

from __future__ import annotations

from pathlib import Path

import click

from gautools._console import log_error, log_header, log_info, log_success, log_warn
from gautools.parsers.log import parse_frequencies, parse_geometry, parse_termination
from gautools.parsers.xyz import write_xyz


@click.command("gau2xyz")
@click.argument("logfiles", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--warn-imag/--no-warn-imag", default=True, show_default=True,
              help="Warn if number of imaginary frequencies ≠ 1 (for TS logs).")
@click.option("--frame", type=click.Choice(["last", "all"]), default="last", show_default=True,
              help="Which geometry frame(s) to extract.")
def main(logfiles: tuple[Path, ...], warn_imag: bool, frame: str) -> None:
    """Extract geometry from Gaussian log file(s) and write XYZ file(s)."""
    log_header("gau2xyz — Geometry Extractor")

    for log_path in logfiles:
        log_info(f"Reading: {log_path}")

        # Termination status
        if parse_termination(log_path):
            log_success("Normal termination")
        else:
            log_warn("Error / incomplete — extracting last available geometry")

        # Imaginary frequency check
        if warn_imag:
            freqs = parse_frequencies(log_path)
            if freqs:
                imag = [f for f in freqs if f < 0]
                if len(imag) == 0:
                    log_warn("No imaginary frequencies found (expected 1 for a TS)")
                elif len(imag) > 1:
                    log_warn(f"{len(imag)} imaginary frequencies found: {imag}")

        # Extract geometry
        try:
            result = parse_geometry(log_path, frame=frame)
        except ValueError as e:
            log_error(str(e))
            continue

        if frame == "all":
            frames = result
            out_path = log_path.with_suffix(".xyz")
            # Write multi-frame XYZ (all frames concatenated)
            lines: list[str] = []
            for i, atoms in enumerate(frames):
                lines.append(str(len(atoms)))
                lines.append(f"Frame {i+1} from {log_path.name}")
                for a in atoms:
                    lines.append(f"{a.symbol:<4} {a.x:12.6f} {a.y:12.6f} {a.z:12.6f}")
            out_path.write_text("\n".join(lines) + "\n")
            log_success(f"Written {len(frames)} frames → {out_path}")
        else:
            atoms = result
            out_path = log_path.with_suffix(".xyz")
            write_xyz(atoms, out_path, comment=f"Generated from {log_path.name}")
            log_success(f"{len(atoms)} atoms → {out_path}")

        click.echo()
