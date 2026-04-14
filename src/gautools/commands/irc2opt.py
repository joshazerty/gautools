"""irc2opt — create optimisation inputs from IRC endpoints."""

from __future__ import annotations

from pathlib import Path

import click

from gautools._console import log_error, log_header, log_info, log_success, log_warn
from gautools.parsers.inp import (
    GaussianInput, find_input_file, parse_gaussian_input, write_gaussian_file,
)
from gautools.parsers.log import parse_irc_endpoints, parse_termination
from gautools.route import route_for_opt


@click.command("irc2opt")
@click.argument("logfile", type=click.Path(exists=True, path_type=Path))
@click.option("--inp", "inp_file", type=click.Path(exists=True, path_type=Path),
              default=None, help="Gaussian input file (auto-detected if omitted).")
@click.option("--suffix-fwd", default="_irc_fwd", show_default=True,
              help="Suffix for the forward endpoint output file.")
@click.option("--suffix-rev", default="_irc_rev", show_default=True,
              help="Suffix for the reverse endpoint output file.")
def main(
    logfile: Path,
    inp_file: Path | None,
    suffix_fwd: str,
    suffix_rev: str,
) -> None:
    """Create Opt+Freq input files for both IRC endpoints."""
    log_header("irc2opt — IRC Endpoint Optimisation Setup")
    log_info(f"Log file: {logfile}")

    if not parse_termination(logfile):
        log_warn("Log does not show Normal termination")

    # Extract endpoints
    try:
        rev_geom, fwd_geom, method = parse_irc_endpoints(logfile)
        log_success(
            f"Extracted {len(rev_geom)}-atom geometries "
            f"(method: {method})"
        )
    except ValueError as e:
        log_error(str(e))
        raise SystemExit(1)

    # Find input file
    resolved_inp = inp_file or find_input_file(logfile)
    if resolved_inp is None:
        log_error("No matching .inp/.gjf/.com found. Use --inp to specify one.")
        raise SystemExit(1)
    log_success(f"Input file: {resolved_inp.name}")

    template = parse_gaussian_input(resolved_inp)
    opt_route = route_for_opt(template.route)
    log_info(f"Route: {opt_route}")

    import re
    clean_stem = re.sub(r"_irc$", "", logfile.stem, flags=re.IGNORECASE)

    for label, geom, suffix in [
        ("reverse", rev_geom, suffix_rev),
        ("forward", fwd_geom, suffix_fwd),
    ]:
        out_path = logfile.parent / f"{clean_stem}{suffix}.inp"
        out_inp = GaussianInput(
            link0=template.link0,
            route=opt_route,
            title=template.title or [f"{label.capitalize()} endpoint"],
            charge_mult=template.charge_mult,
            atoms=[],
            footer=template.footer,
        )
        write_gaussian_file(out_path, out_inp, atoms=geom)
        log_success(f"Written ({label}): {out_path.name}")

    log_header("Done")
