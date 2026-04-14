"""Tests for gautools.route"""

import pytest

from gautools.route import remove_keywords, route_for_irc, route_for_opt, route_for_qst2


class TestRemoveKeywords:
    def test_plain_keyword(self):
        assert "Opt" not in remove_keywords("#p Opt B3LYP", ["Opt"])

    def test_keyword_equals_value(self):
        result = remove_keywords("#p Opt=NoEigenTest B3LYP", ["Opt"])
        assert "Opt" not in result
        assert "B3LYP" in result

    def test_keyword_with_parens(self):
        result = remove_keywords("#p Opt=(TS,CalcFC,NoEigenTest) B3LYP", ["Opt"])
        assert "Opt" not in result
        assert "B3LYP" in result

    def test_case_insensitive(self):
        result = remove_keywords("#p opt B3LYP", ["Opt"])
        assert "opt" not in result.lower()

    def test_multiple_keywords(self):
        result = remove_keywords("#p Opt Freq B3LYP", ["Opt", "Freq"])
        assert "Opt" not in result
        assert "Freq" not in result
        assert "B3LYP" in result

    def test_unrelated_keywords_preserved(self):
        result = remove_keywords("#p Opt B3LYP/6-31G(d)", ["Freq"])
        assert "Opt" in result
        assert "B3LYP" in result

    def test_cleans_extra_whitespace(self):
        result = remove_keywords("#p  Opt  B3LYP", ["Opt"])
        assert "  " not in result


class TestRouteForIrc:
    def test_removes_opt(self):
        r = route_for_irc("#p Opt=(TS,CalcFC) B3LYP")
        assert "Opt" not in r

    def test_removes_freq(self):
        r = route_for_irc("#p B3LYP Freq")
        assert "Freq" not in r

    def test_removes_qst(self):
        r = route_for_irc("#p Opt=(QST2,CalcFC) B3LYP")
        assert "QST" not in r.upper()

    def test_adds_irc_keyword(self):
        r = route_for_irc("#p B3LYP Opt")
        assert "IRC=" in r

    def test_preserves_functional(self):
        r = route_for_irc("#p B3LYP/6-31G(d) Opt Freq")
        assert "B3LYP" in r


class TestRouteForOpt:
    def test_removes_irc(self):
        r = route_for_opt("#p IRC=(CalcFC,MaxPoints=30) B3LYP")
        assert "IRC" not in r

    def test_removes_existing_opt(self):
        r = route_for_opt("#p IRC=(CalcFC) Opt=(MaxCycles=50) B3LYP")
        assert r.count("Opt") == 1  # only the newly added one

    def test_adds_opt_freq(self):
        r = route_for_opt("#p B3LYP IRC=(CalcFC)")
        assert "Opt=" in r
        assert "Freq" in r

    def test_preserves_functional(self):
        r = route_for_opt("#p B3LYP/gen IRC=(CalcFC)")
        assert "B3LYP" in r


class TestRouteForQst2:
    def test_removes_existing_opt(self):
        r = route_for_qst2("#p Opt=(MaxCycles=200) B3LYP")
        assert r.count("Opt") == 1

    def test_adds_qst2(self):
        r = route_for_qst2("#p B3LYP Opt")
        assert "QST2" in r

    def test_adds_calcfc(self):
        r = route_for_qst2("#p B3LYP")
        assert "CalcFC" in r
