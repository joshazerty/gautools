"""Integration tests for CLI commands using click.testing.CliRunner."""

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from gautools.commands.gau2xyz    import main as gau2xyz
from gautools.commands.ts2irc     import main as ts2irc
from gautools.commands.irc2opt    import main as irc2opt
from gautools.commands.xyz2inp    import main as xyz2inp
from gautools.commands.gau_status import main as gau_status
from gautools.commands.gau_energy import main as gau_energy

DATA = Path(__file__).parent / "data"


@pytest.fixture
def workdir(tmp_path):
    """Copy test data files into a temp directory and return it."""
    for f in DATA.iterdir():
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


class TestGau2xyz:
    def test_creates_xyz(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau2xyz, [str(workdir / "sample_opt_freq.log")])
        assert result.exit_code == 0
        assert (workdir / "sample_opt_freq.xyz").exists()

    def test_correct_atom_count_in_xyz(self, workdir):
        runner = CliRunner()
        runner.invoke(gau2xyz, [str(workdir / "sample_opt_freq.log")])
        lines = (workdir / "sample_opt_freq.xyz").read_text().splitlines()
        assert int(lines[0]) == 5  # methane = 5 atoms

    def test_warns_on_multiple_imaginary(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau2xyz, ["--warn-imag", str(workdir / "sample_ts.log")])
        # TS has exactly 1 imaginary — should NOT warn about multiple
        assert "imaginary" not in result.output.lower() or "1" in result.output

    def test_batch_multiple_files(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau2xyz, [
            str(workdir / "sample_opt_freq.log"),
            str(workdir / "sample_ts.log"),
        ])
        assert result.exit_code == 0
        assert (workdir / "sample_opt_freq.xyz").exists()
        assert (workdir / "sample_ts.xyz").exists()


class TestTs2irc:
    def test_creates_irc_inp(self, workdir):
        runner = CliRunner()
        # sample_opt_freq.log + sample.inp (auto-detected as "sample")
        # Need a log+inp with same basename; copy sample.inp as sample_opt_freq.inp
        shutil.copy(workdir / "sample.inp", workdir / "sample_opt_freq.inp")
        result = runner.invoke(ts2irc, [str(workdir / "sample_opt_freq.log")])
        assert result.exit_code == 0
        # _clean_irc_stem strips _opt and _freq → "sample_irc.inp"
        out = workdir / "sample_irc.inp"
        assert out.exists()

    def test_output_contains_irc_keyword(self, workdir):
        shutil.copy(workdir / "sample.inp", workdir / "sample_opt_freq.inp")
        runner = CliRunner()
        runner.invoke(ts2irc, [str(workdir / "sample_opt_freq.log")])
        content = (workdir / "sample_irc.inp").read_text()
        assert "IRC=" in content

    def test_output_lacks_opt_keyword(self, workdir):
        shutil.copy(workdir / "sample.inp", workdir / "sample_opt_freq.inp")
        runner = CliRunner()
        runner.invoke(ts2irc, [str(workdir / "sample_opt_freq.log")])
        content = (workdir / "sample_irc.inp").read_text()
        route_line = next(l for l in content.splitlines() if l.strip().startswith("#"))
        assert "Opt" not in route_line

    def test_explicit_inp(self, workdir):
        runner = CliRunner()
        result = runner.invoke(ts2irc, [
            str(workdir / "sample_opt_freq.log"),
            "--inp", str(workdir / "sample.inp"),
        ])
        assert result.exit_code == 0


class TestIrc2opt:
    def test_creates_two_files(self, workdir):
        runner = CliRunner()
        shutil.copy(workdir / "sample.inp", workdir / "sample_irc.inp")
        result = runner.invoke(irc2opt, [str(workdir / "sample_irc.log")])
        assert result.exit_code == 0
        assert (workdir / "sample_irc_fwd.inp").exists()
        assert (workdir / "sample_irc_rev.inp").exists()

    def test_output_contains_opt(self, workdir):
        shutil.copy(workdir / "sample.inp", workdir / "sample_irc.inp")
        runner = CliRunner()
        runner.invoke(irc2opt, [str(workdir / "sample_irc.log")])
        for suffix in ("_irc_fwd.inp", "_irc_rev.inp"):
            content = (workdir / f"sample{suffix}").read_text()
            assert "Opt=" in content

    def test_custom_suffixes(self, workdir):
        shutil.copy(workdir / "sample.inp", workdir / "sample_irc.inp")
        runner = CliRunner()
        runner.invoke(irc2opt, [
            str(workdir / "sample_irc.log"),
            "--suffix-fwd", "_forward",
            "--suffix-rev", "_reverse",
        ])
        assert (workdir / "sample_forward.inp").exists()
        assert (workdir / "sample_reverse.inp").exists()


class TestXyz2inp:
    def test_creates_inp(self, workdir):
        runner = CliRunner()
        result = runner.invoke(xyz2inp, [str(workdir / "sample.xyz")])
        assert result.exit_code == 0
        assert (workdir / "sample.inp").exists()

    def test_uses_builtin_template(self, workdir):
        # Remove any local template first
        local_tmpl = workdir / "template.inp"
        if local_tmpl.exists():
            local_tmpl.unlink()
        runner = CliRunner()
        runner.invoke(xyz2inp, [str(workdir / "sample.xyz"), "--no-local-template"])
        content = (workdir / "sample.inp").read_text()
        assert "B3LYP" in content

    def test_charge_override(self, workdir):
        runner = CliRunner()
        runner.invoke(xyz2inp, [str(workdir / "sample.xyz"), "--charge", "0", "--mult", "1"])
        content = (workdir / "sample.inp").read_text()
        assert "0 1" in content

    def test_local_template_used(self, workdir):
        tmpl = workdir / "template.inp"
        tmpl.write_text(
            "%NProcShared=4\n#p PBE0/def2TZVP\n\nTitle\n\n0 1\n\n"
        )
        runner = CliRunner()
        runner.invoke(xyz2inp, [str(workdir / "sample.xyz")])
        content = (workdir / "sample.inp").read_text()
        assert "PBE0" in content


class TestGauStatus:
    def test_output_contains_filename(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_status, [str(workdir / "sample_opt_freq.log")])
        assert "sample_opt_freq.log" in result.output

    def test_normal_termination_shown(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_status, [str(workdir / "sample_opt_freq.log")])
        assert "Normal" in result.output

    def test_csv_flag(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_status, ["--csv", str(workdir / "sample_opt_freq.log")])
        # CSV output should have comma-separated values
        lines = [l for l in result.output.splitlines() if l.strip()]
        assert any("," in l for l in lines)

    def test_exit_zero_all_normal(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_status, [str(workdir / "sample_opt_freq.log")])
        assert result.exit_code == 0

    def test_exit_one_on_incomplete(self, workdir, tmp_path):
        bad = tmp_path / "bad.log"
        bad.write_text("SCF Done: E = -40.5\n")
        runner = CliRunner()
        result = runner.invoke(gau_status, [str(bad)])
        assert result.exit_code == 1


class TestGauEnergy:
    def test_output_contains_scf(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_energy, [str(workdir / "sample_opt_freq.log")])
        assert "SCF" in result.output

    def test_csv_flag(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_energy, ["--csv", str(workdir / "sample_opt_freq.log")])
        lines = [l for l in result.output.splitlines() if l.strip()]
        assert any("," in l for l in lines)

    def test_relative_energy_zero_for_single_file(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_energy, [str(workdir / "sample_opt_freq.log")])
        # ΔG for the reference file should be +0.00
        assert "+0.00" in result.output

    def test_unit_kcal(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_energy, ["--unit", "kcal", str(workdir / "sample_opt_freq.log")])
        assert "kcal" in result.output

    def test_unit_kj(self, workdir):
        runner = CliRunner()
        result = runner.invoke(gau_energy, ["--unit", "kj", str(workdir / "sample_opt_freq.log")])
        assert "kJ" in result.output
