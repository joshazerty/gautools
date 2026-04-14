"""ts2irc — set up an IRC calculation from a converged TS log."""

from __future__ import annotations

from pathlib import Path

import click

from gautools._console import log_error, log_header, log_info, log_success, log_warn
from gautools.parsers.inp import find_input_file, parse_gaussian_input, write_gaussian_file
from gautools.parsers.log import parse_geometry, parse_termination
from gautools.route import route_for_irc


def _clean_irc_stem(stem: str) -> str:
    """Strip common TS/opt suffixes so output is named sensibly."""
    import re
    result = stem
    while True:
        prev = result
        result = re.sub(
            r"_(qst[23]|opt|ts|freq|guess)$", "", result, flags=re.IGNORECASE
        )
        if result == prev:
            break
    return result


@click.command("ts2irc")
@click.argument("logfile", type=click.Path(exists=True, path_type=Path))
@click.option("--inp", "inp_file", type=click.Path(exists=True, path_type=Path),
              default=None, help="Gaussian input file (auto-detected if omitted).")
@click.option("--irc-opts", default="CalcFC,MaxPoints=30,StepSize=10", show_default=True,
              help="Options passed to the IRC keyword.")
def main(logfile: Path, inp_file: Path | None, irc_opts: str) -> None:
    """Create an IRC input file from a converged TS/QST2/QST3 log."""
    log_header("ts2irc — IRC Input Generator")
    log_info(f"Log file: {logfile}")

    # Termination check
    if not parse_termination(logfile):
        log_warn("Log does not show Normal termination")

    # Extract geometry
    try:
        atoms = parse_geometry(logfile)
        log_success(f"Extracted {len(atoms)}-atom geometry")
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

    # Build output filename
    clean_stem = _clean_irc_stem(logfile.stem)
    out_path = logfile.parent / f"{clean_stem}_irc.inp"

    # Build modified route
    import re
    base_route = template.route
    base_route = re.sub(r"\bIRC\s*=\s*\([^)]*\)", "", base_route, flags=re.IGNORECASE)
    base_route = re.sub(r"\bIRC\b", "", base_route, flags=re.IGNORECASE)
    new_route = route_for_irc(base_route)
    # Apply custom irc_opts if not default
    if irc_opts != "CalcFC,MaxPoints=30,StepSize=10":
        new_route = re.sub(
            r"IRC=\([^)]*\)", f"IRC=({irc_opts})", new_route, flags=re.IGNORECASE
        )

    from gautools.parsers.inp import GaussianInput
    out_inp = GaussianInput(
        link0=template.link0,
        route=new_route,
        title=template.title or [f"IRC from {logfile.name}"],
        charge_mult=template.charge_mult,
        atoms=[],
        footer=template.footer,
    )

    write_gaussian_file(out_path, out_inp, atoms=atoms)
    log_success(f"Written: {out_path}")
    log_header("Done")
