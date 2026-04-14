"""xyz2inp — convert XYZ file(s) to Gaussian input files."""

from __future__ import annotations

from pathlib import Path

import click

from gautools._console import log_error, log_header, log_info, log_success
from gautools.parsers.inp import GaussianInput, write_gaussian_file
from gautools.parsers.xyz import read_xyz
from gautools.template import get_effective_template


@click.command("xyz2inp")
@click.argument("xyzfiles", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--template", "template_file",
              type=click.Path(exists=True, path_type=Path), default=None,
              help="Explicit template .inp file (overrides auto-detection).")
@click.option("--charge", type=int, default=None,
              help="Override charge from template.")
@click.option("--mult", type=int, default=None,
              help="Override multiplicity from template.")
@click.option("--route", "route_override", default=None,
              help="Override the entire route section.")
@click.option("--no-local-template", is_flag=True, default=False,
              help="Ignore any template.inp in the current directory.")
def main(
    xyzfiles: tuple[Path, ...],
    template_file: Path | None,
    charge: int | None,
    mult: int | None,
    route_override: str | None,
    no_local_template: bool,
) -> None:
    """Convert XYZ file(s) to Gaussian input files using a template."""
    log_header("xyz2inp — XYZ → Gaussian Input")

    # Template search: CWD first, then the directory of the first XYZ file
    # (so template.inp placed alongside the XYZ files is always found).
    if no_local_template:
        search_dir = None
    else:
        cwd = Path.cwd()
        first_parent = xyzfiles[0].parent.resolve() if xyzfiles else cwd
        search_dir = cwd if (cwd / "template.inp").exists() else first_parent
    tmpl = get_effective_template(explicit=template_file, search_dir=search_dir)

    # Apply overrides
    charge_mult = tmpl.charge_mult
    if charge is not None or mult is not None:
        parts = tmpl.charge_mult.split()
        c = str(charge) if charge is not None else parts[0]
        m = str(mult)   if mult   is not None else (parts[1] if len(parts) > 1 else "1")
        charge_mult = f"{c} {m}"

    route = route_override if route_override else tmpl.route

    for xyz_path in xyzfiles:
        out_path = xyz_path.with_suffix(".inp")
        log_info(f"{xyz_path.name} → {out_path.name}")

        try:
            atoms = read_xyz(xyz_path)
        except (ValueError, IndexError) as e:
            log_error(str(e))
            continue

        inp = GaussianInput(
            link0=tmpl.link0_extras,
            route=route,
            title=["Title Card: Optimization"],
            charge_mult=charge_mult,
            atoms=[],
            footer=tmpl.footer.splitlines() if isinstance(tmpl.footer, str) else tmpl.footer,
        )
        write_gaussian_file(out_path, inp, atoms=atoms)
        log_success(f"Created: {out_path.name}")

    log_header("Done")
