"""Template system for xyz2inp.

Resolution order (highest to lowest priority):
  1. Explicit --template CLI flag
  2. ./template.inp  (local project directory)
  3. ~/.gautools/template.inp  (user default)
  4. BUILTIN_TEMPLATE  (hardcoded fallback)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gautools.parsers.inp import GaussianInput, parse_gaussian_input


TEMPLATE_FILENAME = "template.inp"
USER_TEMPLATE_DIR = Path.home() / ".gautools"


@dataclass
class TemplateConfig:
    route: str
    charge_mult: str
    link0_extras: list[str]  # %mem, %NProcShared (not %chk — always auto-set)
    footer: str


# The built-in default — B3LYP-D3BJ/def2SVP+SDD, PCM(1-Pentanol), charge -1 1
BUILTIN_TEMPLATE = TemplateConfig(
    route=(
        "#p B3LYP/gen pseudo=read EmpiricalDispersion=GD3BJ Int=UltraFine "
        "SCF=(MaxCycle=512,XQC) SCRF=(PCM,Solvent=1-Pentanol) "
        "Opt(MaxCycles=2000,CalcFC) Freq"
    ),
    charge_mult="-1 1",
    link0_extras=["%NProcShared=8", "%mem=24000MB"],
    footer=(
        "C O H 0\n"
        "def2SVP\n"
        "****\n"
        "Re 0\n"
        "SDD\n"
        "****\n"
        "\n"
        "Re 0\n"
        "SDD\n"
    ),
)


def find_template(search_dir: Path | None = None) -> Path | None:
    """Return the highest-priority template.inp path, or None if none exist."""
    dirs = []
    if search_dir is not None:
        dirs.append(Path(search_dir))
    else:
        dirs.append(Path.cwd())
    dirs.append(USER_TEMPLATE_DIR)

    for d in dirs:
        candidate = d / TEMPLATE_FILENAME
        if candidate.exists():
            return candidate
    return None


def load_template(path: Path) -> TemplateConfig:
    """Read a template.inp file and return a TemplateConfig."""
    inp: GaussianInput = parse_gaussian_input(path)
    extras = [l for l in inp.link0 if not l.lower().startswith("%chk")]
    footer = "\n".join(inp.footer)
    return TemplateConfig(
        route=inp.route,
        charge_mult=inp.charge_mult,
        link0_extras=extras,
        footer=footer,
    )


def get_effective_template(
    explicit: Path | None = None,
    search_dir: Path | None = None,
) -> TemplateConfig:
    """Return the effective template using the full resolution chain.

    Parameters
    ----------
    explicit:
        A path explicitly passed via ``--template``.  Always wins.
    search_dir:
        Directory to check for a local ``template.inp`` (defaults to CWD).
    """
    if explicit is not None:
        return load_template(Path(explicit))

    found = find_template(search_dir)
    if found is not None:
        return load_template(found)

    return BUILTIN_TEMPLATE


def write_default_template(dest_dir: Path = USER_TEMPLATE_DIR) -> Path:
    """Write the built-in template to dest_dir/template.inp and return the path."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / TEMPLATE_FILENAME

    content = (
        f"{chr(10).join(BUILTIN_TEMPLATE.link0_extras)}\n"
        f"%chk=BASENAME.chk\n"
        f"{BUILTIN_TEMPLATE.route}\n"
        "\n"
        "Title Card Required\n"
        "\n"
        f"{BUILTIN_TEMPLATE.charge_mult}\n"
        "\n"
        f"{BUILTIN_TEMPLATE.footer}\n"
    )
    dest.write_text(content)
    return dest
