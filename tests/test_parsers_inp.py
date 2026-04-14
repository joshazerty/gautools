"""Tests for gautools.parsers.inp"""

from pathlib import Path

import pytest

from gautools.parsers.inp import (
    GaussianInput,
    find_input_file,
    parse_gaussian_input,
    write_gaussian_file,
)
from gautools.parsers.log import Atom

DATA = Path(__file__).parent / "data"


class TestParseGaussianInput:
    def test_route_extracted(self):
        inp = parse_gaussian_input(DATA / "sample.inp")
        assert "B3LYP" in inp.route
        assert "Opt" in inp.route

    def test_charge_mult(self):
        inp = parse_gaussian_input(DATA / "sample.inp")
        assert inp.charge_mult.strip() == "-1 1"

    def test_link0_contains_chk(self):
        inp = parse_gaussian_input(DATA / "sample.inp")
        assert any("%chk" in l.lower() for l in inp.link0)

    def test_footer_preserved(self):
        inp = parse_gaussian_input(DATA / "sample.inp")
        # sample.inp has no explicit footer section, footer may be empty
        assert isinstance(inp.footer, list)

    def test_atoms_parsed(self):
        inp = parse_gaussian_input(DATA / "sample.inp")
        assert len(inp.atoms) == 5
        assert inp.atoms[0].symbol == "C"


class TestFindInputFile:
    def test_exact_match(self, tmp_path):
        inp = tmp_path / "ts.inp"
        inp.write_text("%chk=ts.chk\n#p B3LYP\n\nTitle\n\n0 1\nH 0 0 0\n\n")
        log = tmp_path / "ts.log"
        log.write_text("")
        assert find_input_file(log) == inp

    def test_suffix_stripping_irc(self, tmp_path):
        inp = tmp_path / "ts.inp"
        inp.write_text("%chk=ts.chk\n#p B3LYP\n\nTitle\n\n0 1\nH 0 0 0\n\n")
        log = tmp_path / "ts_irc.log"
        log.write_text("")
        assert find_input_file(log) == inp

    def test_suffix_stripping_opt(self, tmp_path):
        inp = tmp_path / "mol.inp"
        inp.write_text("%chk=mol.chk\n#p B3LYP\n\nTitle\n\n0 1\nH 0 0 0\n\n")
        log = tmp_path / "mol_opt.log"
        log.write_text("")
        assert find_input_file(log) == inp

    def test_returns_none_when_absent(self, tmp_path):
        log = tmp_path / "missing.log"
        log.write_text("")
        assert find_input_file(log) is None


class TestWriteGaussianFile:
    def test_creates_file(self, tmp_path):
        inp = parse_gaussian_input(DATA / "sample.inp")
        atoms = [Atom("C", 0.0, 0.0, 0.0), Atom("H", 1.0, 0.0, 0.0)]
        out = tmp_path / "out.inp"
        write_gaussian_file(out, inp, atoms=atoms)
        assert out.exists()

    def test_chk_updated(self, tmp_path):
        inp = parse_gaussian_input(DATA / "sample.inp")
        out = tmp_path / "myfile.inp"
        write_gaussian_file(out, inp, atoms=inp.atoms)
        content = out.read_text()
        assert "%chk=myfile.chk" in content

    def test_route_preserved(self, tmp_path):
        inp = parse_gaussian_input(DATA / "sample.inp")
        out = tmp_path / "out.inp"
        write_gaussian_file(out, inp, atoms=inp.atoms)
        content = out.read_text()
        assert "B3LYP" in content

    def test_roundtrip(self, tmp_path):
        original = parse_gaussian_input(DATA / "sample.inp")
        out = tmp_path / "rt.inp"
        write_gaussian_file(out, original, atoms=original.atoms)
        reparsed = parse_gaussian_input(out)
        assert reparsed.charge_mult.strip() == original.charge_mult.strip()
        assert "B3LYP" in reparsed.route
        assert len(reparsed.atoms) == len(original.atoms)
