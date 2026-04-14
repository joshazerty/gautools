"""gautools — umbrella Click group."""

from __future__ import annotations

import click

from gautools import __version__
from gautools.commands.gau2xyz   import main as gau2xyz
from gautools.commands.ts2irc    import main as ts2irc
from gautools.commands.irc2opt   import main as irc2opt
from gautools.commands.scan2qst2 import main as scan2qst2
from gautools.commands.xyz2inp   import main as xyz2inp
from gautools.commands.gau_status import main as gau_status
from gautools.commands.gau_energy import main as gau_energy


@click.group()
@click.version_option(__version__, prog_name="gautools")
def cli() -> None:
    """gautools — Gaussian 16 workflow utilities.

    \b
    Typical workflow:
      xyz2inp   mol.xyz              # XYZ → Gaussian input
      scan2qst2 scan.log             # scan → PES plot + QST2 input
      ts2irc    ts.log               # TS → IRC input
      irc2opt   ts_irc.log           # IRC → endpoint opt inputs
      gau2xyz   any.log              # log → XYZ

    \b
    Analysis:
      gau-status *.log               # batch status table
      gau-energy ts.log rev.log fwd.log  # energy comparison table
    """


cli.add_command(gau2xyz,    name="gau2xyz")
cli.add_command(ts2irc,     name="ts2irc")
cli.add_command(irc2opt,    name="irc2opt")
cli.add_command(scan2qst2,  name="scan2qst2")
cli.add_command(xyz2inp,    name="xyz2inp")
cli.add_command(gau_status, name="gau-status")
cli.add_command(gau_energy, name="gau-energy")


@cli.command("init")
def init_cmd() -> None:
    """Create ~/.gautools/template.inp from the built-in default template."""
    from gautools.template import write_default_template
    path = write_default_template()
    click.echo(f"Template written to: {path}")
    click.echo("Edit it to set your default route, charge/mult, and basis set.")
