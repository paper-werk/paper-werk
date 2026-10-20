"""Aufrufe an ``docker`` und ``docker compose``."""

from __future__ import annotations

import os
import subprocess
from typing import List, Sequence, Tuple

from paperwerk.ausgabe import Abbruch, meld
from paperwerk.installation import Installation


def container(projekt: str, alle: bool = False) -> List[Tuple[str, str]]:
    """(Name, Status) der Container mit dem Compose-Label ``projekt``.
    Ohne Docker oder ohne laufenden Daemon: leere Liste."""
    befehl = ["docker", "ps", "--filter", f"label=com.docker.compose.project={projekt}",
              "--format", "{{.Names}}\t{{.Status}}"]
    if alle:
        befehl.insert(2, "-a")
    try:
        lauf = subprocess.run(befehl, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return []
    if lauf.returncode != 0:
        return []
    paare = []
    for zeile in lauf.stdout.splitlines():
        if zeile.strip():
            name, _, status = zeile.partition("\t")
            paare.append((name, status))
    return paare


def laeuft(projekt: str) -> bool:
    return bool(container(projekt))


def compose(inst: Installation, argumente: Sequence[str], env_pflicht: bool = True) -> int:
    """Führt ``docker compose <dateien> <argumente>`` für ``inst`` aus und gibt den
    Exit-Code zurück. Ohne ``.env`` startet kein Dienst sinnvoll, deshalb bricht
    jeder Aufruf außer ``command`` vorher ab."""
    if env_pflicht and not inst.hat_env:
        raise Abbruch(
            f"{inst.env_datei} fehlt. Anlegen aus den Vorlagen config-template/.env*.example "
            "und danach durchsehen; ohne ausgefüllte Werte startet nichts."
        )
    befehl = inst.compose_befehl() + list(argumente)
    meld(f"{inst.anzeigename} (-p {inst.projekt})", "stack")
    umgebung = dict(os.environ)
    umgebung.update(inst.compose_umgebung())
    try:
        return subprocess.run(befehl, env=umgebung).returncode
    except FileNotFoundError:
        raise Abbruch("docker nicht gefunden") from None
