"""Abgleich der ``.env``-Dateien einer Installation mit ``config-template/.env*.example``.

Python-Fassung von ``setup/env-abgleich.sh``, Begründung dort. Verglichen
werden nur Schlüsselnamen, nie Werte. Auskommentierte Schlüssel der Vorlage
(``# KEY=``) gelten als Angebot, nicht als Pflicht.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, NamedTuple, Set

from paperwerk.ausgabe import Abbruch

_AKTIV = re.compile(r"^([A-Z][A-Z0-9_]*)=")
_AUSKOMMENTIERT = re.compile(r"^# *([A-Z][A-Z0-9_]*)=")


class Abgleich(NamedTuple):
    datei: str
    vorhanden: bool
    fehlend: List[str]
    angebote: List[str]


def _schluessel(datei: Path, muster: "re.Pattern[str]") -> Set[str]:
    text = datei.read_text(encoding="utf-8", errors="replace")
    return {m.group(1) for m in map(muster.match, text.splitlines()) if m}


def abgleichen(vorlagen: Path, projektordner: Path) -> List[Abgleich]:
    ergebnisse = []
    for vorlage in sorted(vorlagen.glob(".env*.example")):
        name = vorlage.name[: -len(".example")]
        ziel = projektordner / name
        if not ziel.is_file():
            ergebnisse.append(Abgleich(name, False, [], []))
            continue
        vorhanden = _schluessel(ziel, _AKTIV)
        ergebnisse.append(Abgleich(
            name, True,
            sorted(_schluessel(vorlage, _AKTIV) - vorhanden),
            sorted(_schluessel(vorlage, _AUSKOMMENTIERT) - vorhanden),
        ))
    return ergebnisse


def bericht(ergebnisse: List[Abgleich]) -> List[str]:
    """Textzeilen wie in ``env-abgleich.sh``; Abbruch, wenn die Installation
    keine einzige ``.env``-Datei hat."""
    if not any(e.vorhanden for e in ergebnisse):
        raise Abbruch("Keine .env-Datei der Installation gefunden. Stimmt der Projektordner?")
    zeilen = []
    offen = 0
    for e in ergebnisse:
        if not e.vorhanden:
            zeilen.append(f"{e.datei}: in der Installation nicht vorhanden")
        elif not e.fehlend and not e.angebote:
            zeilen.append(f"{e.datei}: vollständig")
        else:
            zeilen.append(e.datei)
            zeilen += [f"  fehlt:   {k}" for k in e.fehlend]
            zeilen += [f"  Angebot: {k}" for k in e.angebote]
            offen += len(e.fehlend)
    if offen:
        zeilen.append(f"{offen} Schlüssel fehlen. Begründung jeweils als Kommentar in der "
                      "Vorlage unter config-template/; nicht jeder Schlüssel passt zu jedem Host.")
    return zeilen
