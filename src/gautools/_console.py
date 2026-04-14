"""Terminal output helpers — colours, symbols, logging functions.

Respects the NO_COLOR environment variable (https://no-color.org/).
"""

import os
import sys


def _colour_enabled() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


class _Colors:
    HEADER  = "\033[95m"
    OKBLUE  = "\033[94m"
    OKCYAN  = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL    = "\033[91m"
    ENDC    = "\033[0m"
    BOLD    = "\033[1m"

    def __getattribute__(self, name: str) -> str:
        val = super().__getattribute__(name)
        if not _colour_enabled():
            return ""
        return val


Colors = _Colors()


def _sym(code: str, char: str) -> str:
    if _colour_enabled():
        return f"{code}{char}{Colors.ENDC}"
    return char


TICK  = _sym(Colors.OKGREEN if _colour_enabled() else "", "✔")
CROSS = _sym(Colors.FAIL    if _colour_enabled() else "", "✘")
WARN  = _sym(Colors.WARNING if _colour_enabled() else "", "⚠")
INFO  = _sym(Colors.OKCYAN  if _colour_enabled() else "", "ℹ")


def _rebuild_symbols() -> None:
    """Rebuild symbols after import (call if NO_COLOR changes at runtime)."""
    global TICK, CROSS, WARN, INFO
    TICK  = _sym(Colors.OKGREEN, "✔")
    CROSS = _sym(Colors.FAIL,    "✘")
    WARN  = _sym(Colors.WARNING, "⚠")
    INFO  = _sym(Colors.OKCYAN,  "ℹ")


def log_header(title: str) -> None:
    if _colour_enabled():
        print(f"\n{Colors.HEADER}{'='*60}\n {title}\n{'='*60}{Colors.ENDC}")
    else:
        print(f"\n{'='*60}\n {title}\n{'='*60}")


def log_info(msg: str) -> None:
    print(f" {INFO}  {msg}")


def log_success(msg: str) -> None:
    print(f" {TICK}  {msg}")


def log_error(msg: str) -> None:
    print(f" {CROSS}  {msg}", file=sys.stderr)


def log_warn(msg: str) -> None:
    print(f" {WARN}  {msg}")
