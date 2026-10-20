"""Gemeinsamer Zugriff auf die Paperless-API für die Export-Skripte in helpers/.

Wird von views_exportieren.py und document_types_exportieren.py eingebunden,
nicht direkt ausgeführt. Rein lesend.
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def lade_conf(pfad: Path) -> dict:
    """Liest KEY="wert"-Zeilen aus der setup.conf (eine Shell-Datei, hier nur
    die einfachen Zuweisungen)."""
    werte = {}
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^([A-Z0-9_]+)=(?:"([^"]*)"|(\S*))', zeile)
        if m:
            werte[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
    return werte


def oeffne_projekt(projekt: str):
    """Liefert eine Funktion api(pfad) für eine Installation.

    `projekt` ist der Name wie bei stack.sh (dev, kunde) oder "config" für
    config/; gesucht wird in derselben Reihenfolge wie in
    setup/lib/installation.sh.
    """
    wurzel = Path(__file__).resolve().parent.parent
    if projekt == "config":
        kandidaten = [wurzel / "config"]
    else:
        kandidaten = [wurzel / "config-repos" / f"paper-werk-config-{projekt}",
                      wurzel / "projekte" / f"paper-werk-config-{projekt}",
                      wurzel / "projekte" / projekt]
    ordner = next((k for k in kandidaten if k.is_dir()), None)
    if ordner is None:
        sys.exit(f"Installation nicht gefunden: {projekt}")
    conf_pfad = ordner / "einstellungen" / "setup.conf"
    if not conf_pfad.is_file():
        sys.exit(f"setup.conf nicht gefunden: {conf_pfad}")
    conf = lade_conf(conf_pfad)
    container = conf.get("PAPERLESS_CONTAINER")
    token = conf.get("PAPERLESS_TOKEN")
    if not container or not token:
        sys.exit("PAPERLESS_CONTAINER oder PAPERLESS_TOKEN fehlt in der setup.conf")

    def api(pfad: str) -> dict:
        # Der Aufruf läuft im Paperless-Container gegen localhost:8000, wie in
        # setup/lib/common.sh: ohne Caddy, ohne Zertifikat, ohne Port.
        r = subprocess.run(
            ["docker", "exec", container, "curl", "-sf",
             "-H", f"Authorization: Token {token}",
             f"http://localhost:8000{pfad}"],
            capture_output=True)
        if r.returncode != 0:
            sys.exit(f"Abruf gescheitert: {pfad} (läuft der Stack? Token gültig?)")
        return json.loads(r.stdout.decode("utf-8"))

    return api


def gebe_json_aus(daten) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(daten, ensure_ascii=False, indent=2))
