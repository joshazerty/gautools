"""Read and write XYZ coordinate files."""

from __future__ import annotations

from pathlib import Path

from gautools.parsers.log import Atom


def read_xyz(filepath: Path) -> list[Atom]:
    """Parse a standard XYZ file and return a list of Atoms."""
    filepath = Path(filepath)
    lines = filepath.read_text().splitlines()
    try:
        n_atoms = int(lines[0].strip())
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Invalid XYZ file (bad atom count): {filepath}") from exc

    atoms: list[Atom] = []
    for i in range(2, 2 + n_atoms):
        parts = lines[i].split()
        if len(parts) < 4:
            raise ValueError(f"Bad coordinate line {i+1} in {filepath}: {lines[i]!r}")
        atoms.append(Atom(symbol=parts[0], x=float(parts[1]), y=float(parts[2]), z=float(parts[3])))
    return atoms


def write_xyz(atoms: list[Atom], filepath: Path, comment: str = "") -> None:
    """Write atoms to an XYZ file."""
    filepath = Path(filepath)
    lines = [str(len(atoms)), comment]
    for a in atoms:
        lines.append(f"{a.symbol:<4} {a.x:12.6f} {a.y:12.6f} {a.z:12.6f}")
    filepath.write_text("\n".join(lines) + "\n")
