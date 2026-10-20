"""Benannte Volumes der Vorlage und der Umzug aus Bind-Ordnern.

Bis Oktober 2026 waren alle Volumes Bind-Ordner unter ``PAPER_WERK_DATA_ROOT``
und ``KOPIA_DATA_ROOT`` (``driver_opts: o: bind``). Seitdem verwaltet Docker
sie selbst. ``umziehen`` überträgt eine bestehende Installation: Container
entfernen (``down``, ohne ``-v``), die Bind-Volumes entfernen (die Ordner auf
dem Host bleiben unberührt), die Volumes neu anlegen und den Inhalt der Ordner
mit ``cp -a`` hineinkopieren. Besitzer und Rechte bleiben dabei erhalten,
auch unter Docker Desktop (Postgres 999, Paperless 1000, App 10001).

Die alten Ordner bleiben als Rückfall stehen, bis jemand sie löscht.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from paperwerk.ausgabe import Abbruch, meld
from paperwerk.installation import Installation

#: Hilfsabbild für das Kopieren; klein und überall verfügbar.
KOPIERER = "docker.io/library/alpine:3.20"


def volumes_der_vorlage(wurzel: Path) -> List[str]:
    """Namen im ``volumes:``-Block von ``compose/docker-compose.yml``, in
    Dateireihenfolge. Gelesen als Text: Die CLI kommt ohne YAML-Bibliothek aus,
    und der Block ist eine flache Liste ``  name:``."""
    text = (wurzel / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    block = re.search(r"(?m)^volumes:\n((?:(?:  [^\n]*|\s*#[^\n]*|)\n)*)", text)
    if not block:
        raise Abbruch("compose/docker-compose.yml hat keinen volumes-Block")
    return re.findall(r"(?m)^  ([a-z0-9][a-z0-9_-]*):\s*$", block.group(1))


def alter_ordner(name: str, daten: str, kopia: str) -> str:
    """Ordner auf dem Host, in dem ein Volume im alten Aufbau lag."""
    if name.startswith("kopia-"):
        return f"{kopia.rstrip('/')}/{name[len('kopia-'):]}"
    return f"{daten.rstrip('/')}/{name}"


def _docker(*argumente: str, pruefen: bool = True) -> subprocess.CompletedProcess:
    try:
        lauf = subprocess.run(["docker", *argumente], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        raise Abbruch("docker nicht gefunden") from None
    if pruefen and lauf.returncode != 0:
        raise Abbruch(f"docker {' '.join(argumente)}: {lauf.stderr.strip()}")
    return lauf


def bind_ordner(volume: str) -> Optional[str]:
    """``device`` eines Bind-Volumes, ``None`` für ein verwaltetes Volume,
    ``""`` wenn es das Volume nicht gibt."""
    lauf = _docker("volume", "inspect", volume, pruefen=False)
    if lauf.returncode != 0:
        return ""
    optionen = json.loads(lauf.stdout)[0].get("Options") or {}
    return optionen.get("device") if optionen.get("o") == "bind" else None


def laufende_dienste(projekt: str) -> List[str]:
    """Compose-Dienste von ``projekt`` mit laufendem Container, sortiert."""
    lauf = _docker("ps", "--filter", f"label=com.docker.compose.project={projekt}",
                   "--format", '{{.Label "com.docker.compose.service"}}', pruefen=False)
    return sorted({z for z in lauf.stdout.split() if z}) if lauf.returncode == 0 else []


def plan(inst: Installation, namen: List[str]) -> List[Tuple[str, str]]:
    """(Volume, alter Ordner) für jedes Volume, das noch ein Bind-Ordner ist."""
    schritte = []
    for name in namen:
        volume = f"{inst.projekt}_{name}"
        ordner = bind_ordner(volume)
        if ordner:
            schritte.append((volume, ordner))
    return schritte


def umziehen(inst: Installation, compose, trocken: bool = False) -> List[str]:
    """Zieht ``inst`` von Bind-Ordnern auf benannte Volumes um. ``compose`` ist
    ``docker.compose`` (als Parameter, damit Tests ohne Docker auskommen)."""
    namen = volumes_der_vorlage(inst.wurzel)
    if inst.env_wert("PAPER_WERK_CONSUME_ORDNER"):
        namen = [n for n in namen if n != "consume"]
    schritte = plan(inst, namen)
    if not schritte:
        return [f"{inst.anzeigename}: keine Bind-Volumes, nichts umzuziehen."]
    bericht = [f"{inst.anzeigename} (-p {inst.projekt}): {len(schritte)} Volume(s) umziehen"]
    bericht += [f"  {volume:<34} aus {ordner}" for volume, ordner in schritte]
    if trocken:
        return bericht + ["Trocken: nichts geändert."]

    def schritt(text: str, code: int) -> None:
        if code:
            raise Abbruch(f"{text} fehlgeschlagen (Code {code}); die alten Ordner sind unverändert.")

    # Danach startet nur, was vorher lief: lasttest etwa läuft ohne n8n und
    # Caddy, ein "up -d" für alles stieße dort an die Ports von dev.
    laufend = laufende_dienste(inst.projekt)
    meld("Container entfernen (down, Volumes und Ordner bleiben)")
    schritt("down", compose(inst, ["down"]))
    for volume, ordner in schritte:
        _docker("volume", "rm", volume)
        # Mit den Labels, die Compose selbst setzt; sonst warnt es bei jedem
        # Start, das Volume sei nicht von ihm angelegt.
        _docker("volume", "create", "--label", f"com.docker.compose.project={inst.projekt}",
                "--label", f"com.docker.compose.volume={volume[len(inst.projekt) + 1:]}", volume)
        meld(f"{volume} <- {ordner}")
        _docker("run", "--rm", "-v", f"{volume}:/ziel", "-v", f"{ordner}:/quelle:ro",
                KOPIERER, "sh", "-c", "cp -a /quelle/. /ziel/")
    if laufend:
        meld(f"Starten: {' '.join(laufend)}")
        schritt("up -d", compose(inst, ["up", "-d", *laufend]))
    else:
        bericht.append("Lief vorher nicht und wurde nicht gestartet.")
    return bericht + [
        "Umgezogen. Die alten Ordner liegen unverändert und sind ab jetzt ungenutzt.",
        "Nach einer Prüfung (doctor, Anmeldung, ein Beleg, ein Dokument) löschen und",
        "PAPER_WERK_DATA_ROOT und KOPIA_DATA_ROOT aus .env entfernen.",
    ]
