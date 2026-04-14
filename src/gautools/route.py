"""Route string manipulation — add/remove Gaussian keywords."""

import re


def remove_keywords(route: str, keywords: list[str]) -> str:
    """Remove keyword(s) from a Gaussian route string (case-insensitive).

    Handles all three common forms:
      KEYWORD
      KEYWORD=value
      KEYWORD=(opt1,opt2,...)
    """
    r = route
    for kw in keywords:
        r = re.sub(rf"\b{kw}\s*=\s*\([^)]*\)", "", r, flags=re.IGNORECASE)
        r = re.sub(rf"\b{kw}\s*=\s*\S+",       "", r, flags=re.IGNORECASE)
        r = re.sub(rf"\b{kw}\b",               "", r, flags=re.IGNORECASE)
    return " ".join(r.split())


def route_for_irc(route: str) -> str:
    """Remove Opt/Freq/QST* from route and append IRC=(CalcFC,MaxPoints=30,StepSize=10)."""
    r = remove_keywords(route, [r"Opt", r"Freq", r"QST\d"])
    return f"{r} IRC=(CalcFC,MaxPoints=30,StepSize=10)"


def route_for_opt(route: str) -> str:
    """Remove IRC/Opt/Freq from route and append Opt=(CalcFC,MaxCycles=200) Freq."""
    r = remove_keywords(route, [r"IRC", r"Opt", r"Freq"])
    return f"{r} Opt=(CalcFC,MaxCycles=200) Freq"


def route_for_qst2(route: str) -> str:
    """Remove existing Opt from route and append Opt=(QST2,CalcFC)."""
    r = remove_keywords(route, [r"Opt"])
    return f"{r} Opt=(QST2,CalcFC)"
