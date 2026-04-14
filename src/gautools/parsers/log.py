"""Parse Gaussian 16 log / output files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Atom:
    symbol: str
    x: float
    y: float
    z: float

    def format(self) -> str:
        return f" {self.symbol:<2} {self.x:>14.8f} {self.y:>14.8f} {self.z:>14.8f}"


@dataclass
class LogEnergies:
    scf_hartree: float | None = None
    zpe_hartree: float | None = None    # "Zero-point correction"
    e_zpe: float | None = None          # "Sum of electronic and zero-point Energies"
    enthalpy: float | None = None       # "Sum of electronic and thermal Enthalpies"
    gibbs: float | None = None          # "Sum of electronic and thermal Free Energies"


@dataclass
class LogStatus:
    normal_termination: bool
    n_atoms: int
    imaginary_frequencies: list[float] = field(default_factory=list)
    has_freq: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ATOM_RE = re.compile(
    r"^\s+\d+\s+(\d+)\s+\d+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)"
)


def _read_lines(filepath: Path) -> list[str]:
    return Path(filepath).read_text(errors="replace").splitlines()


def _parse_orientation_block(lines: list[str], start: int) -> list[Atom]:
    """Parse one Standard/Input orientation table starting at the header line."""
    from gautools._constants import get_symbol
    frame: list[Atom] = []
    i = start + 5  # skip 4-line header + separator
    while i < len(lines):
        if "---" in lines[i]:
            break
        m = _ATOM_RE.match(lines[i])
        if m:
            frame.append(Atom(
                symbol=get_symbol(int(m.group(1))),
                x=float(m.group(2)),
                y=float(m.group(3)),
                z=float(m.group(4)),
            ))
        i += 1
    return frame


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_geometry(filepath: Path, frame: str = "last") -> list[Atom]:
    """Extract geometry frame(s) from a Gaussian log file.

    Parameters
    ----------
    filepath:
        Path to the .log / .out file.
    frame:
        ``"last"`` (default) returns the final orientation table.
        ``"all"`` returns every orientation table as a flat list of frames
        (each frame is a list[Atom]) — in this case the return type is
        ``list[list[Atom]]``.
    """
    lines = _read_lines(filepath)
    frames: list[list[Atom]] = []

    for i, line in enumerate(lines):
        if "Standard orientation:" in line or "Input orientation:" in line:
            f = _parse_orientation_block(lines, i)
            if f:
                frames.append(f)

    if not frames:
        raise ValueError(f"No geometry found in {filepath}")

    if frame == "all":
        return frames  # type: ignore[return-value]
    return frames[-1]


def parse_irc_endpoints(
    filepath: Path,
) -> tuple[list[Atom], list[Atom], str]:
    """Extract the final geometry of the FORWARD and REVERSE IRC directions.

    Returns
    -------
    (reverse_geom, forward_geom, method)
        ``method`` is ``"directed"`` when direction markers were found,
        ``"fallback"`` otherwise.
    """
    lines = _read_lines(filepath)

    reverse_geoms: list[list[Atom]] = []
    forward_geoms:  list[list[Atom]] = []
    all_geoms:      list[list[Atom]] = []
    direction: str | None = None

    i = 0
    while i < len(lines):
        line = lines[i]
        if re.search(r"Following the Reaction Path in the REVERSE", line, re.IGNORECASE):
            direction = "reverse"
        elif re.search(r"Following the Reaction Path in the FORWARD", line, re.IGNORECASE):
            direction = "forward"

        if "Standard orientation:" in line or "Input orientation:" in line:
            f = _parse_orientation_block(lines, i)
            if f:
                all_geoms.append(f)
                if direction == "reverse":
                    reverse_geoms.append(f)
                elif direction == "forward":
                    forward_geoms.append(f)
        i += 1

    if reverse_geoms and forward_geoms:
        return reverse_geoms[-1], forward_geoms[-1], "directed"

    if len(all_geoms) >= 3:
        return all_geoms[1], all_geoms[-1], "fallback"

    raise ValueError(
        f"Not enough geometries in IRC output (found {len(all_geoms)}, need ≥ 3): {filepath}"
    )


def parse_frequencies(filepath: Path) -> list[float]:
    """Return all vibrational frequencies from a Gaussian freq calculation.

    Negative values indicate imaginary modes.
    Returns an empty list if no freq block is present.
    """
    lines = _read_lines(filepath)
    freqs: list[float] = []
    for line in lines:
        if line.strip().startswith("Frequencies --"):
            parts = line.split("--")[1].split()
            freqs.extend(float(p) for p in parts)
    return freqs


def parse_termination(filepath: Path) -> bool:
    """Return True if the log file ends with Normal termination."""
    lines = _read_lines(filepath)
    return any("Normal termination" in l for l in lines[-20:])


def parse_energies(filepath: Path) -> LogEnergies:
    """Extract thermochemical energies from a Gaussian log file."""
    lines = _read_lines(filepath)
    energies = LogEnergies()

    for line in lines:
        s = line.strip()
        # SCF energy — last "SCF Done" wins
        if s.startswith("SCF Done"):
            m = re.search(r"=\s*(-?\d+\.\d+)", s)
            if m:
                energies.scf_hartree = float(m.group(1))
        elif s.startswith("Zero-point correction"):
            m = re.search(r"=\s*(-?\d+\.\d+)", s)
            if m:
                energies.zpe_hartree = float(m.group(1))
        elif s.startswith("Sum of electronic and zero-point Energies"):
            m = re.search(r"=\s*(-?\d+\.\d+)", s)
            if m:
                energies.e_zpe = float(m.group(1))
        elif s.startswith("Sum of electronic and thermal Enthalpies"):
            m = re.search(r"=\s*(-?\d+\.\d+)", s)
            if m:
                energies.enthalpy = float(m.group(1))
        elif s.startswith("Sum of electronic and thermal Free Energies"):
            m = re.search(r"=\s*(-?\d+\.\d+)", s)
            if m:
                energies.gibbs = float(m.group(1))

    return energies


def get_log_status(filepath: Path) -> LogStatus:
    """Return a summary of a log file's status, atom count, and imaginary frequencies."""
    normal = parse_termination(filepath)
    try:
        geom = parse_geometry(filepath)
        n_atoms = len(geom)
    except ValueError:
        n_atoms = 0

    freqs = parse_frequencies(filepath)
    imag  = [f for f in freqs if f < 0]

    return LogStatus(
        normal_termination=normal,
        n_atoms=n_atoms,
        imaginary_frequencies=imag,
        has_freq=len(freqs) > 0,
    )
