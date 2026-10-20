"""Zustandsbericht einer Installation (``paper-werk doctor <name>``).

Python-Fassung von ``setup/doktor.sh``; Zweck und Fragen dort. Der Bericht
ändert nichts und braucht kein Netz. Unterschied zur Shell-Fassung: Das
Zertifikat wird über das ``ssl``-Modul gelesen, ``openssl`` ist nicht nötig.
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from paperwerk import docker
from paperwerk.ausgabe import GELB, GRUEN, LEISE, ROT, faerben
from paperwerk.env_abgleich import abgleichen, bericht
from paperwerk.installation import Installation

AUSGELIEFERT = ["compose", "config-template", "setup", "n8n", "starterpakete", "demodaten"]
BREITE = 12
#: Kopia-Quelle der Installation (compose/docker-compose.yml, Dienst kopia).
KOPIA_QUELLE = "/source/paper-werk"
#: Älter als das ist der letzte Snapshot verdächtig: täglicher Zeitplan plus Spielraum.
SNAPSHOT_HOECHSTALTER_H = 26


def _git(wurzel: Path, *argumente: str) -> Optional[str]:
    try:
        lauf = subprocess.run(["git", "-C", str(wurzel), *argumente],
                              capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return None
    return lauf.stdout.rstrip("\n") if lauf.returncode == 0 else None


def _zeile(marke: str, text: str) -> str:
    return f"{marke:<{BREITE}} {text}"


def _achtung(marke: str, text: str) -> str:
    return _zeile(marke, faerben(f"⚠ {text}", GELB))


def _fehler(marke: str, text: str) -> str:
    return _zeile(marke, faerben(f"✖ {text}", ROT))


def _eingerueckt(text: str) -> List[str]:
    return [" " * (BREITE + 1) + z for z in text.splitlines()]


def zertifikat_ablauf(host: str, port: int = 443, timeout: float = 5) -> Optional[float]:
    """Ablaufzeitpunkt (Unix-Zeit) des Zertifikats, das ``host`` ausliefert, oder
    None. Ohne Prüfung der Kette: Im Modus ``intern`` stellt Caddy selbst aus."""
    kontext = ssl.create_default_context()
    kontext.check_hostname = False
    kontext.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout) as roh:
            with kontext.wrap_socket(roh, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
    except OSError:
        return None
    if not der:
        return None
    # getpeercert() liefert ohne Verifikation kein dict; die Felder gibt es nur
    # über _test_decode_cert, das eine Datei verlangt. Privat, aber seit 3.x stabil.
    datei = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    try:
        datei.write(ssl.DER_cert_to_PEM_cert(der))
        datei.close()
        felder = ssl._ssl._test_decode_cert(datei.name)  # type: ignore[attr-defined]
    except (ssl.SSLError, AttributeError, ValueError):
        return None
    finally:
        os.unlink(datei.name)
    return ssl.cert_time_to_seconds(felder["notAfter"])


def _stand(wurzel: Path) -> List[str]:
    if _git(wurzel, "rev-parse", "--git-dir") is None:
        return [_achtung("Stand", "kein Git-Arbeitsverzeichnis, Stand nicht feststellbar")]
    zeilen = [
        _zeile("Stand", _git(wurzel, "log", "-1", "--format=%h  \"%s\"  (%ad)", "--date=short") or "?"),
        _zeile("", f"Zweig {_git(wurzel, 'rev-parse', '--abbrev-ref', 'HEAD')}"),
    ]
    oben = _git(wurzel, "rev-parse", "--abbrev-ref", "@{upstream}")
    if oben is None:
        return zeilen + [_zeile("", "kein Gegenstück im Netz eingetragen")]
    hinter = _git(wurzel, "rev-list", "--count", "HEAD..@{upstream}") or "?"
    vor = _git(wurzel, "rev-list", "--count", "@{upstream}..HEAD") or "?"
    if hinter != "0":
        zeilen.append(_achtung("", f"{hinter} Commits hinter {oben}, Stand von vor dem letzten Abruf"))
    if vor != "0":
        zeilen.append(_achtung("", f"{vor} eigene Commits, die nirgends sonst liegen"))
    return zeilen


def _ausgeliefert(wurzel: Path, inst: Installation) -> List[str]:
    if _git(wurzel, "rev-parse", "--git-dir") is None:
        return []
    zeilen: List[str] = []
    geaendert = []
    for ordner in AUSGELIEFERT:
        if not (wurzel / ordner).is_dir():
            continue
        aenderungen = _git(wurzel, "status", "--porcelain", "--", ordner)
        if aenderungen:
            geaendert.append(ordner)
            anzahl = len(aenderungen.splitlines())
            zeilen.append(_achtung("Ausgeliefert", f"{ordner}/: {anzahl} Datei(en) geändert:"))
            zeilen += _eingerueckt(aenderungen)
    if not geaendert:
        return [_zeile("Ausgeliefert", faerben(f"unverändert ({' '.join(AUSGELIEFERT)})", GRUEN))]
    for ordner in geaendert:
        zeilen += _eingerueckt(_git(wurzel, "--no-pager", "diff", "--stat", "--", ordner) or "")
    zeilen += [
        _zeile("", "(?? heißt: neue Datei, M heißt: an einer von uns geändert)"),
        _zeile("", f"Änderungen gehören in {inst.ordner.relative_to(inst.wurzel).as_posix()}/compose.override.yml,"),
        _zeile("", "nicht in die ausgelieferten Dateien, sonst kollidiert der nächste Abruf."),
    ]
    return zeilen


def _eigenes(inst: Installation) -> List[str]:
    zeilen: List[str] = []
    if inst.neuer_aufbau:
        c = inst.conf
        text = f"instanz.conf: Projekt {c['PROJEKT']}, HTTPS {c['HTTPS']}"
        if c["PROFILE"]:
            text += f", Profile {c['PROFILE']}"
        if c["ZUSATZ"]:
            text += f", Zusatz {c['ZUSATZ']}"
        zeilen.append(_zeile("Eigenes", text))
    else:
        zeilen.append(_achtung("Eigenes", "keine instanz.conf, alter Aufbau mit eigener docker-compose.yml"))

    override = inst.ordner / "compose.override.yml"
    if override.is_file():
        dienste = sum(1 for z in override.read_text(encoding="utf-8").splitlines()
                      if re.match(r"^\s{2}[a-z-]+:", z))
        zeilen.append(_zeile("", f"compose.override.yml vorhanden ({dienste} Dienste berührt)"))

    if not inst.hat_env:
        zeilen.append(_fehler("", ".env fehlt, ohne sie startet nichts"))
    zeilen.append(_zeile("", "Abgleich der .env-Dateien mit den Vorlagen:"))
    try:
        zeilen += _eingerueckt("\n".join(bericht(abgleichen(inst.wurzel / "config-template", inst.ordner))))
    except Exception as fehler:  # Bericht soll weiterlaufen, auch wenn der Abgleich scheitert
        zeilen += _eingerueckt(str(fehler))
    return zeilen


def _container(inst: Installation) -> List[str]:
    alle = docker.container(inst.projekt, alle=True)
    if not alle:
        return [_achtung("Container", f"keine; nie gestartet, Docker nicht erreichbar oder anderer Name (-p {inst.projekt})")]
    laufend = [c for c in alle if c[1].startswith("Up ")]
    zeilen = [_zeile("Container", f"{len(laufend)} von {len(alle)} laufen")]
    zeilen += [" " * (BREITE + 1) + faerben("⚠", GELB) + f" {n}\t{s}"
               for n, s in alle if not s.startswith("Up ")]
    return zeilen


def _https(inst: Installation, jetzt: float) -> List[str]:
    if not inst.https:
        return []
    host = inst.env_wert("PAPER_WERK_HOSTNAME")
    modus = inst.env_wert("PAPER_WERK_TLS_MODE") or "intern"
    zeilen = [_zeile("HTTPS", f"Name {host or '?'}, Zertifikat {modus}")]
    if not host:
        return zeilen
    ablauf = zertifikat_ablauf(host)
    if ablauf is None:
        return zeilen + [_achtung("", "kein Zertifikat abrufbar; läuft Caddy, und zeigt der Name hierher?")]
    bis = time.strftime("%Y-%m-%d %H:%M", time.localtime(ablauf))
    tage = int((ablauf - jetzt) // 86400)
    if modus == "intern":
        # Caddys eigene CA stellt Blätter mit 12 h Laufzeit aus und erneuert
        # selbst; 0 Tage Rest ist der Normalfall.
        if tage < 0:
            return zeilen + [_achtung("", "Zertifikat abgelaufen und nicht erneuert; läuft Caddy?")]
        return zeilen + [_zeile("", f"Zertifikat von Caddy selbst, erneuert sich automatisch (gültig bis {bis})")]
    if tage < 0:
        return zeilen + [_fehler("", f"Zertifikat ABGELAUFEN seit {-tage} Tagen")]
    if tage < 30:
        return zeilen + [_achtung("", f"Zertifikat läuft in {tage} Tagen ab; Ersatz bei der IT anfordern")]
    return zeilen + [_zeile("", f"Zertifikat gültig bis {bis} ({tage} Tage)")]


def snapshot_zeit(text: str) -> Optional[float]:
    """Kopias ``startTime`` (RFC 3339 mit Nanosekunden, etwa
    ``2026-10-17T21:00:03.556012603Z``) als Unix-Zeit."""
    treffer = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(Z|[+-]\d\d:\d\d)$", text or "")
    if not treffer:
        return None
    zone = "+00:00" if treffer.group(2) == "Z" else treffer.group(2)
    return datetime.fromisoformat(treffer.group(1) + zone).timestamp()


def _sicherung(inst: Installation, jetzt: float) -> List[str]:
    """Alter des letzten Snapshots der Quelle. Die nächtliche Sicherung ist
    Kopias eigener Zeitplan; fällt er aus, meldet Kopia das nicht von sich aus."""
    behaelter = f"{inst.projekt}-kopia-1"
    if not any(n == behaelter and s.startswith("Up ") for n, s in docker.container(inst.projekt)):
        return [_achtung("Sicherung", f"Kopia läuft nicht ({behaelter})")]
    try:
        lauf = subprocess.run(["docker", "exec", behaelter, "kopia", "snapshot", "list", KOPIA_QUELLE, "--json"],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return [_achtung("Sicherung", "Kopia antwortet nicht")]
    if lauf.returncode != 0:
        if "not connected" in lauf.stderr:
            return [_achtung("Sicherung", "Kopia ist mit keinem Repository verbunden; es wird nichts gesichert")]
        return [_achtung("Sicherung", f"Kopia: {lauf.stderr.strip()[:120]}")]
    try:
        zeiten = [snapshot_zeit(s.get("startTime")) for s in json.loads(lauf.stdout or "[]")]
    except ValueError:
        return [_achtung("Sicherung", "Antwort von Kopia nicht lesbar")]
    zeiten = [z for z in zeiten if z]
    if not zeiten:
        return [_achtung("Sicherung", f"noch kein Snapshot von {KOPIA_QUELLE}")]
    letzte = max(zeiten)
    stunden = (jetzt - letzte) / 3600
    text = f"letzter Snapshot {time.strftime('%Y-%m-%d %H:%M', time.localtime(letzte))} ({stunden:.0f} h)"
    if stunden > SNAPSHOT_HOECHSTALTER_H:
        return [_achtung("Sicherung", text + "; läuft der Zeitplan in Kopia?")]
    return [_zeile("Sicherung", text)]


def doktor(inst: Installation) -> List[str]:
    jetzt = time.time()
    kopf = f"paper-werk: Zustand der Installation \"{inst.anzeigename}\""
    zeilen = ["", kopf + faerben(f"          {datetime.now():%Y-%m-%d %H:%M}", LEISE), ""]
    for abschnitt in (_stand(inst.wurzel), _ausgeliefert(inst.wurzel, inst), _eigenes(inst)):
        zeilen += abschnitt + [""]
    zeilen += _container(inst) + _https(inst, jetzt) + _sicherung(inst, jetzt) + [""]
    return zeilen
