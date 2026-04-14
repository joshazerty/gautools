"""Parse and write Gaussian input (.inp / .gjf / .com) files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gautools.parsers.log import Atom


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class GaussianInput:
    link0: list[str]       # %chk=..., %mem=..., %NProcShared=...
    route: str             # full route section as a single string
    title: list[str]
    charge_mult: str       # e.g. "-1 1"
    atoms: list[Atom]      # empty for template files
    footer: list[str]      # basis set section, ModRedundant, etc.


# ---------------------------------------------------------------------------
# Find matching input file
# ---------------------------------------------------------------------------

_STRIP_SUFFIXES = (
    r"_(qst[23]|opt|ts|freq|irc|guess|scan|log|out)$"
)


def find_input_file(log_path: Path) -> Path | None:
    """Locate the .inp/.gjf/.com file corresponding to a given log file.

    Search order:
    1. Exact basename match.
    2. Strip one known suffix (_opt, _ts, _freq, _qst2, _irc, _guess, _scan,
       _log, _out) and retry.  Repeat until no more suffixes can be stripped.
    """
    log_path = Path(log_path)
    parent   = log_path.parent
    base     = log_path.stem

    candidates = [base]
    # keep stripping suffixes
    current = base
    while True:
        stripped = re.sub(_STRIP_SUFFIXES, "", current, flags=re.IGNORECASE)
        if stripped == current:
            break
        candidates.append(stripped)
        current = stripped

    for stem in candidates:
        for ext in (".inp", ".gjf", ".com"):
            p = parent / (stem + ext)
            if p.exists():
                return p

    return None


# ---------------------------------------------------------------------------
# Parse input file
# ---------------------------------------------------------------------------

def parse_gaussian_input(inp_path: Path) -> GaussianInput:
    """Parse a Gaussian input file into a GaussianInput dataclass.

    State machine: header → route_end_check → title → charge → geom → footer
    """
    lines = Path(inp_path).read_text(errors="replace").splitlines()

    header_lines: list[str] = []
    title_lines:  list[str] = []
    charge_mult   = ""
    atoms:        list[Atom] = []
    footer_lines: list[str] = []

    state = "header"

    for line in lines:
        stripped = line.strip()

        if state == "header":
            header_lines.append(line.rstrip())
            if stripped.startswith("#"):
                state = "route_end_check"

        elif state == "route_end_check":
            if not stripped or stripped.startswith("---"):
                state = "title"
            else:
                header_lines.append(line.rstrip())

        elif state == "title":
            if not stripped:
                state = "charge"
            else:
                title_lines.append(line.rstrip())

        elif state == "charge":
            if stripped:
                charge_mult = line.rstrip()
                state = "geom"

        elif state == "geom":
            if not stripped:
                state = "footer"
            else:
                parts = stripped.split()
                if len(parts) == 4:
                    try:
                        atoms.append(Atom(
                            symbol=parts[0],
                            x=float(parts[1]),
                            y=float(parts[2]),
                            z=float(parts[3]),
                        ))
                    except ValueError:
                        pass  # connectivity / modredundant lines

        elif state == "footer":
            footer_lines.append(line.rstrip())

    link0  = [l for l in header_lines if l.strip().startswith("%")]
    route_lines = [
        l for l in header_lines
        if l.strip().startswith("#") or (l.strip() and not l.strip().startswith("%"))
    ]
    route = " ".join(route_lines)

    return GaussianInput(
        link0=link0,
        route=route,
        title=title_lines,
        charge_mult=charge_mult,
        atoms=atoms,
        footer=footer_lines,
    )


# ---------------------------------------------------------------------------
# Write input file
# ---------------------------------------------------------------------------

def write_gaussian_file(
    output_path: Path,
    inp: GaussianInput,
    atoms: list[Atom] | None = None,
    update_chk: bool = True,
) -> None:
    """Write a Gaussian input file.

    Parameters
    ----------
    output_path:
        Destination path.
    inp:
        Template GaussianInput (route, charge_mult, footer are taken from here).
    atoms:
        Geometry to write.  Falls back to ``inp.atoms`` if None.
    update_chk:
        Replace (or add) ``%chk=`` with one derived from ``output_path.stem``.
    """
    output_path = Path(output_path)
    geom = atoms if atoms is not None else inp.atoms

    # Build Link0
    link0 = [l for l in inp.link0 if not l.lower().startswith("%chk")]
    if update_chk:
        link0.insert(0, f"%chk={output_path.stem}.chk")

    lines: list[str] = []
    for l in link0:
        lines.append(l)
    lines.append(inp.route)
    lines.append("")
    for t in inp.title:
        lines.append(t)
    lines.append("")
    lines.append(inp.charge_mult)
    for a in geom:
        lines.append(a.format())
    lines.append("")
    for l in inp.footer:
        lines.append(l)
    # Ensure trailing newline
    if lines and lines[-1].strip():
        lines.append("")

    output_path.write_text("\n".join(lines) + "\n")
