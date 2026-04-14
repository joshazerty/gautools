"""Tests for gautools.parsers.log"""

from pathlib import Path

import pytest

from gautools.parsers.log import (
    get_log_status,
    parse_energies,
    parse_frequencies,
    parse_geometry,
    parse_irc_endpoints,
    parse_termination,
)

DATA = Path(__file__).parent / "data"


class TestParseTermination:
    def test_normal(self):
        assert parse_termination(DATA / "sample_opt_freq.log") is True

    def test_incomplete(self, tmp_path):
        f = tmp_path / "incomplete.log"
        f.write_text("Some output\nSCF Done: E = -40.5\n")
        assert parse_termination(f) is False


class TestParseGeometry:
    def test_correct_n_atoms_methane(self):
        atoms = parse_geometry(DATA / "sample_opt_freq.log")
        assert len(atoms) == 5

    def test_symbols(self):
        atoms = parse_geometry(DATA / "sample_opt_freq.log")
        symbols = [a.symbol for a in atoms]
        assert symbols[0] == "C"
        assert all(s == "H" for s in symbols[1:])

    def test_last_frame(self):
        # IRC log has 4 geometry blocks; last should be the last forward step
        atoms = parse_geometry(DATA / "sample_irc.log")
        assert len(atoms) == 3
        # Last forward frame has x=-0.2 for atom 0
        assert abs(atoms[0].x - (-0.200000)) < 1e-5

    def test_all_frames(self):
        frames = parse_geometry(DATA / "sample_irc.log", frame="all")
        assert len(frames) == 4

    def test_no_geometry_raises(self, tmp_path):
        f = tmp_path / "empty.log"
        f.write_text("Nothing here\n")
        with pytest.raises(ValueError, match="No geometry"):
            parse_geometry(f)


class TestParseFrequencies:
    def test_no_imaginary_methane(self):
        freqs = parse_frequencies(DATA / "sample_opt_freq.log")
        assert len(freqs) > 0
        assert all(f > 0 for f in freqs)

    def test_one_imaginary_ts(self):
        freqs = parse_frequencies(DATA / "sample_ts.log")
        imag = [f for f in freqs if f < 0]
        assert len(imag) == 1

    def test_no_freq_section(self, tmp_path):
        f = tmp_path / "nofreq.log"
        f.write_text("SCF Done: E = -40.5\n")
        assert parse_frequencies(f) == []


class TestParseEnergies:
    def test_scf_hartree(self):
        e = parse_energies(DATA / "sample_opt_freq.log")
        assert e.scf_hartree is not None
        assert e.scf_hartree < 0

    def test_gibbs(self):
        e = parse_energies(DATA / "sample_opt_freq.log")
        assert e.gibbs is not None
        # G < E+ZPE because entropy lowers free energy below zero-point enthalpy
        assert e.gibbs < e.e_zpe

    def test_zpe(self):
        e = parse_energies(DATA / "sample_opt_freq.log")
        assert e.zpe_hartree is not None
        assert e.zpe_hartree > 0

    def test_missing_returns_none(self, tmp_path):
        f = tmp_path / "empty.log"
        f.write_text("Nothing\n")
        e = parse_energies(f)
        assert e.scf_hartree is None
        assert e.gibbs is None


class TestParseIrcEndpoints:
    def test_directed_method(self):
        rev, fwd, method = parse_irc_endpoints(DATA / "sample_irc.log")
        assert method == "directed"

    def test_correct_n_atoms(self):
        rev, fwd, _ = parse_irc_endpoints(DATA / "sample_irc.log")
        assert len(rev) == 3
        assert len(fwd) == 3

    def test_endpoints_differ(self):
        rev, fwd, _ = parse_irc_endpoints(DATA / "sample_irc.log")
        assert rev[0].x != fwd[0].x

    def test_reverse_is_last_reverse_frame(self):
        rev, _, _ = parse_irc_endpoints(DATA / "sample_irc.log")
        assert abs(rev[0].x - 0.200000) < 1e-5

    def test_forward_is_last_forward_frame(self):
        _, fwd, _ = parse_irc_endpoints(DATA / "sample_irc.log")
        assert abs(fwd[0].x - (-0.200000)) < 1e-5

    def test_fallback_method(self, tmp_path):
        # Build a log with no direction markers but ≥3 geometry blocks
        content = ""
        for x in [0.0, 0.1, 0.2]:
            content += f"""
                         Standard orientation:
 ---------------------------------------------------------------------
 Center     Atomic      Atomic             Coordinates (Angstroms)
 Number     Number       Type             X           Y           Z
 ---------------------------------------------------------------------
      1          6           0        {x:.6f}    0.000000    0.000000
 ---------------------------------------------------------------------
"""
        f = tmp_path / "fallback_irc.log"
        f.write_text(content)
        rev, fwd, method = parse_irc_endpoints(f)
        assert method == "fallback"
        assert len(rev) == 1
        assert len(fwd) == 1

    def test_too_few_geoms_raises(self, tmp_path):
        f = tmp_path / "short.log"
        f.write_text("Not enough data\n")
        with pytest.raises(ValueError):
            parse_irc_endpoints(f)


class TestGetLogStatus:
    def test_normal_methane(self):
        st = get_log_status(DATA / "sample_opt_freq.log")
        assert st.normal_termination is True
        assert st.n_atoms == 5
        assert len(st.imaginary_frequencies) == 0
        assert st.has_freq is True

    def test_ts_has_one_imaginary(self):
        st = get_log_status(DATA / "sample_ts.log")
        assert st.normal_termination is True
        assert len(st.imaginary_frequencies) == 1
        assert st.imaginary_frequencies[0] < 0
