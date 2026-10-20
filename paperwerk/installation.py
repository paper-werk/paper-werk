"""Eine Installation und ihr ``docker compose``-Aufruf.

Python-Fassung von ``stack.sh`` und ``setup/lib/installation.sh``. Beide lesen
dieselbe ``instanz.conf`` und müssen denselben Aufruf ergeben, solange es beide
gibt (``tests/test_installation.py`` prüft die Reihenfolge der ``-f``-Dateien).

Orte: ``config/`` ist die Installation des Rechners und hat keinen Namen;
``config-repos/paper-werk-config-<name>`` sind benannte Installationen (mehrere
auf einem Rechner). Rückfall für ältere Installationen:
``projekte/paper-werk-config-<name>`` und ``projekte/<name>``. Ein Name an
mehreren Orten ist ein Abbruch.

Regeln, die aus ``stack.sh`` übernommen sind:

* Vorlage ``compose/docker-compose.yml``, bei ``HTTPS=ja`` dazu
  ``compose/compose.https.yml``, bei ``APP_BAUEN=ja`` ``compose.build.yml``, mit
  ``PAPER_WERK_CONSUME_ORDNER`` in ``.env`` ``compose.consume-ordner.yml``,
  dann die Dateien aus ``ZUSATZ``, zuletzt
  ``compose.override.yml`` (der Betreiber hat das letzte Wort).
* Alle ``-f``-Pfade absolut: Compose löst sie gegen das Aufrufverzeichnis auf,
  nicht gegen ``--project-directory``.
* ``PAPER_WERK_CADDY_DIR`` und ``PAPER_WERK_APP_CONTEXT`` werden nur gesetzt,
  wenn ``.env`` sie nicht selbst nennt.
* Alter Aufbau: eigene ``docker-compose.yml`` im Installationsordner, sonst nichts.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from paperwerk.ausgabe import Abbruch

_ZUWEISUNG = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

CONF_VORGABEN = {"HTTPS": "nein", "PROFILE": "", "ZUSATZ": "", "ZUSATZREPOS": "", "APP_BAUEN": "nein"}

KONFIG = "config"
REPOS = "config-repos"
PRAEFIX = "paper-werk-config-"
#: Compose-Projektname von config/, wenn instanz.conf keinen nennt.
PROJEKT_KONFIG = "paper-werk"


def _wert(roh: str) -> str:
    roh = roh.strip()
    if roh[:1] in ("'", '"'):
        ende = roh.find(roh[0], 1)
        return roh[1:ende] if ende > 0 else roh[1:]
    kommentar = roh.find(" #")
    if kommentar >= 0:
        roh = roh[:kommentar]
    return roh.strip()


def lies_zuweisungen(datei: Path, streng: bool = False) -> Dict[str, str]:
    """``KEY=Wert``-Zeilen einer Shell-Datei als dict; Kommentare und Leerzeilen
    werden übergangen.

    ``streng`` ist für ``instanz.conf``: Die Datei wird von Bash per ``source``
    und hier per Parser gelesen. Jede Zeile, die keine einfache Zuweisung ist,
    würde beide Leser auseinanderlaufen lassen und ist deshalb ein Abbruch.
    ``.env`` liest nicht streng; dort zählen nur einzelne Schlüssel.
    """
    werte: Dict[str, str] = {}
    text = datei.read_text(encoding="utf-8", errors="replace")
    for nr, zeile in enumerate(text.splitlines(), 1):
        s = zeile.strip()
        if not s or s.startswith("#"):
            continue
        treffer = _ZUWEISUNG.match(zeile)
        if not treffer:
            if streng:
                raise Abbruch(f"{datei}:{nr}: keine einfache Zuweisung KEY=Wert: {s}")
            continue
        werte[treffer.group(1)] = _wert(treffer.group(2))
    return werte


def hostpfad(pfad: Path) -> str:
    """Absoluter Pfad in der Form, die Docker auf jedem Host annimmt
    (unter Windows ``C:/...``, wie ``pwd -W`` in ``stack.sh``)."""
    return pfad.resolve().as_posix()


def kandidaten(wurzel: Path, name: str) -> List[Path]:
    """Mögliche Ordner einer Installation in der Reihenfolge der Auflösung;
    ``name == ""`` steht für ``config/``."""
    if not name:
        return [wurzel / KONFIG]
    return [wurzel / REPOS / f"{PRAEFIX}{name}",
            wurzel / "projekte" / f"{PRAEFIX}{name}",
            wurzel / "projekte" / name]


class Installation:
    """Installationsordner mit ``instanz.conf`` (Vorlage) oder eigener
    ``docker-compose.yml`` (alter Aufbau). ``name`` ist leer für ``config/``."""

    def __init__(self, wurzel: Path, name: str, ordner: Optional[Path] = None):
        self.wurzel = wurzel
        self.name = name
        self.ordner = ordner if ordner is not None else kandidaten(wurzel, name)[0]
        self._conf: Optional[Dict[str, str]] = None

    def __repr__(self) -> str:
        return f"Installation({self.anzeigename!r})"

    @property
    def anzeigename(self) -> str:
        return self.name or KONFIG

    @property
    def neuer_aufbau(self) -> bool:
        return (self.ordner / "instanz.conf").is_file()

    @property
    def gueltig(self) -> bool:
        return self.neuer_aufbau or (self.ordner / "docker-compose.yml").is_file()

    @property
    def env_datei(self) -> Path:
        return self.ordner / ".env"

    @property
    def hat_env(self) -> bool:
        return self.env_datei.is_file()

    @property
    def conf(self) -> Dict[str, str]:
        if self._conf is None:
            werte = dict(CONF_VORGABEN, PROJEKT=self.name or PROJEKT_KONFIG)
            if self.neuer_aufbau:
                werte.update(lies_zuweisungen(self.ordner / "instanz.conf", streng=True))
            self._conf = werte
        return self._conf

    @property
    def projekt(self) -> str:
        """Compose-Projektname (``-p``); steht in Containernamen und Labels und
        ist nicht immer der Ordnername (``kunde`` läuft etwa als
        ``paper-werk-kunde``)."""
        return self.conf["PROJEKT"]

    @property
    def https(self) -> bool:
        return self.conf["HTTPS"] == "ja"

    def env_wert(self, schluessel: str) -> Optional[str]:
        if not self.hat_env:
            return None
        return lies_zuweisungen(self.env_datei).get(schluessel)

    def compose_dateien(self) -> List[Path]:
        if not self.neuer_aufbau:
            datei = self.ordner / "docker-compose.yml"
            if not datei.is_file():
                raise Abbruch(f"{self.ordner} hat weder instanz.conf noch docker-compose.yml")
            return [datei]

        dateien = [self.wurzel / "compose" / "docker-compose.yml"]
        if self.https:
            dateien.append(self.wurzel / "compose" / "compose.https.yml")
        # Vor ZUSATZ: eine Installation kann dort den Namen des gebauten Images ändern.
        if self.conf["APP_BAUEN"] == "ja":
            dateien.append(self.wurzel / "compose" / "compose.build.yml")
        if self.env_wert("PAPER_WERK_CONSUME_ORDNER"):
            dateien.append(self.wurzel / "compose" / "compose.consume-ordner.yml")
        for zusatz in self.conf["ZUSATZ"].split():
            datei = self.ordner / zusatz
            if not datei.is_file():
                raise Abbruch(
                    f'In instanz.conf steht ZUSATZ="{zusatz}", aber die Datei fehlt: {datei}'
                )
            dateien.append(datei)
        override = self.ordner / "compose.override.yml"
        if override.is_file():
            dateien.append(override)
        return dateien

    def compose_umgebung(self) -> Dict[str, str]:
        """Umgebungsvariablen, die zum Compose-Aufruf dazukommen."""
        if not self.neuer_aufbau:
            return {}
        umgebung: Dict[str, str] = {}
        env = lies_zuweisungen(self.env_datei) if self.hat_env else {}

        if "PAPER_WERK_CADDY_DIR" not in env:
            eigene = self.ordner / "caddy"
            caddy = eigene if eigene.is_dir() else self.wurzel / "compose" / "caddy"
            umgebung["PAPER_WERK_CADDY_DIR"] = hostpfad(caddy)

        # Build-Kontext der App: das Nachbar-Repo. Der relative Vorgabewert in
        # der Vorlage würde gegen den Installationsordner aufgelöst.
        if "PAPER_WERK_APP_CONTEXT" not in env:
            app = self.wurzel.parent / "paper-werk-app"
            if (app / "Dockerfile").is_file():
                umgebung["PAPER_WERK_APP_CONTEXT"] = hostpfad(app)
        return umgebung

    def compose_befehl(self) -> List[str]:
        befehl = ["docker", "compose"]
        for datei in self.compose_dateien():
            befehl += ["-f", hostpfad(datei)]
        if self.neuer_aufbau:
            for profil in self.conf["PROFILE"].split():
                befehl += ["--profile", profil]
        befehl += ["--project-directory", hostpfad(self.ordner), "-p", self.projekt]
        return befehl


def installationen(wurzel: Path, mit_konfig: bool = True) -> List[Installation]:
    """``config/`` (falls vorhanden und ``mit_konfig``) und alle benannten
    Installationen, nach Namen sortiert; ``paper-werk-config-archiv`` und
    ``projekte/archiv`` zählen nicht."""
    gefunden: List[Installation] = []
    if mit_konfig:
        konfig = Installation(wurzel, "")
        if konfig.gueltig:
            gefunden.append(konfig)
    namen = set()
    for basis in (wurzel / REPOS, wurzel / "projekte"):
        if basis.is_dir():
            for ordner in basis.iterdir():
                name = ordner.name[len(PRAEFIX):] if ordner.name.startswith(PRAEFIX) else ordner.name
                if ordner.is_dir() and name != "archiv":
                    namen.add(name)
    for name in sorted(namen):
        try:
            inst = finde(wurzel, name)
        except Abbruch:
            continue
        if inst.gueltig:
            gefunden.append(inst)
    return gefunden


def finde(wurzel: Path, name: Optional[str]) -> Installation:
    """Die Installation zu ``name``; ohne Namen ``config/``."""
    name = name or ""
    treffer = [k for k in kandidaten(wurzel, name) if k.is_dir()]
    if name == "archiv" or not treffer:
        vorhanden = ", ".join(i.anzeigename for i in installationen(wurzel)) or "keine"
        was = f"Keine Installation: {name}" if name else "Kein config/ und kein Name angegeben"
        raise Abbruch(f"{was} (vorhanden: {vorhanden})")
    if len(treffer) > 1:
        orte = ", ".join(str(t.relative_to(wurzel)) for t in treffer)
        raise Abbruch(f'Installation "{name}" liegt mehrfach vor: {orte}. Bis auf einen entfernen.')
    return Installation(wurzel, name, treffer[0])


def ist_installation(wurzel: Path, wort: str) -> bool:
    """Ob ``wort`` eine benannte Installation ist; trennt ``up dev`` von ``up --build``."""
    return bool(wort) and any(i.name == wort for i in installationen(wurzel, mit_konfig=False))
