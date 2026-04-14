"""Tests for gautools.parsers.xyz"""

from pathlib import Path

import pytest

from gautools.parsers.log import Atom
from gautools.parsers.xyz import read_xyz, write_xyz

DATA = Path(__file__).parent / "data"


class TestReadXyz:
    def test_correct_n_atoms(self):
        atoms = read_xyz(DATA / "sample.xyz")
        assert len(atoms) == 5

    def test_symbols(self):
        atoms = read_xyz(DATA / "sample.xyz")
        assert atoms[0].symbol == "C"
        assert all(a.symbol == "H" for a in atoms[1:])

    def test_coordinates(self):
        atoms = read_xyz(DATA / "sample.xyz")
        assert abs(atoms[0].x) < 1e-6
        assert abs(atoms[1].x - 0.631339) < 1e-5

    def test_bad_file_raises(self, tmp_path):
        f = tmp_path / "bad.xyz"
        f.write_text("not a number\ncomment\nC 0 0 0\n")
        with pytest.raises(ValueError):
            read_xyz(f)


class TestWriteXyz:
    def test_roundtrip(self, tmp_path):
        original = read_xyz(DATA / "sample.xyz")
        out = tmp_path / "out.xyz"
        write_xyz(original, out, comment="test")
        recovered = read_xyz(out)
        assert len(recovered) == len(original)
        for a, b in zip(original, recovered):
            assert a.symbol == b.symbol
            assert abs(a.x - b.x) < 1e-5
            assert abs(a.y - b.y) < 1e-5
            assert abs(a.z - b.z) < 1e-5

    def test_comment_line(self, tmp_path):
        atoms = [Atom("C", 0.0, 0.0, 0.0)]
        out = tmp_path / "c.xyz"
        write_xyz(atoms, out, comment="hello world")
        lines = out.read_text().splitlines()
        assert lines[1] == "hello world"
