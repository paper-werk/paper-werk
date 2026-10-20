"""Ausgabe auf dem Terminal: Farben, Meldungen, Abbruch.

Farben nur auf einem Terminal und ohne ``NO_COLOR``; ein umgeleiteter
Bericht (``doctor kunde > bericht.txt``) bleibt damit frei von Steuerzeichen.
"""

from __future__ import annotations

import os
import sys

ROT = "1;31"
GRUEN = "1;32"
GELB = "1;33"
BLAU = "1;34"
CYAN = "0;36"
LEISE = "2"


class Abbruch(Exception):
    """Fachlicher Abbruch mit Meldung für den Bediener; ``cli.main`` gibt ihn als
    ``[Fehler]`` aus und endet mit Exit-Code 1. Kein Traceback."""


def farbig(strom=None) -> bool:
    strom = strom or sys.stdout
    return "NO_COLOR" not in os.environ and hasattr(strom, "isatty") and strom.isatty()


def faerben(text: str, code: str, strom=None) -> str:
    if not farbig(strom):
        return text
    return f"\033[{code}m{text}\033[0m"


def meld(text: str, marke: str = "paper-werk") -> None:
    """Statusmeldung auf stderr, damit stdout für Nutzdaten frei bleibt."""
    print(f"{faerben('[' + marke + ']', BLAU, sys.stderr)} {text}", file=sys.stderr)


def fehler(text: str) -> None:
    print(f"{faerben('[Fehler]', ROT, sys.stderr)} {text}", file=sys.stderr)


def utf8_ausgabe() -> None:
    """Stellt stdout/stderr auf UTF-8 um. Unter Windows schreibt Python sonst in
    der ANSI-Codepage, und ``●``/``⚠`` enden als UnicodeEncodeError."""
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
