"""``paper-werk init``: eine neue Installation aus ``config-template/`` anlegen.

Ergebnis ist ein Installationsordner, der nach dem Ausfüllen der gemeldeten
Werte startet:

* ``.env*`` aus den ``*.example``; Kennwörter und Schlüssel mit dem Wert
  ``change-me`` werden erzeugt, alles andere bleibt Vorlage.
* ``einstellungen/setup.conf``, ``n8n/config.json`` und ``n8n/workflows.list``
  aus den ``*.example``; die Containernamen folgen ``PROJEKT``.
* das Paperless-Starterpaket aus ``starterpakete/basis`` plus Variante, nach
  denselben Regeln wie ``setup/paperless/starterpaket-zusammenstellen.sh``.

Ein vorhandener Ordner ist ein Abbruch: ``init`` überschreibt nie.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
from pathlib import Path
from typing import Callable, List, Optional

from paperwerk.ausgabe import Abbruch
from paperwerk.installation import KONFIG, PRAEFIX, PROJEKT_KONFIG, REPOS

PLATZHALTER = "change-me"
#: Schlüssel, deren Platzhalter ``init`` durch einen Zufallswert ersetzt.
ERZEUGT = re.compile(r"(PASSWORD|SECRET_KEY)$")
#: Platzhalter-Präfix der Containernamen in setup.conf.example.
BEISPIEL_PROJEKT = "kunde-xyz"
STARTERPAKET = ["correspondents", "custom_fields", "document_types", "saved_views",
                "storage_paths", "tags", "workflows"]
_ZEILE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _schreibe(datei: Path, text: str) -> None:
    """UTF-8 mit LF, auch unter Windows (``newline=`` kennt write_text erst ab 3.10)."""
    datei.write_bytes(text.encode("utf-8"))


def _env_aus_vorlage(vorlage: Path, ziel: Path, zufall: Callable[[], str]) -> List[str]:
    """Schreibt ``ziel`` aus ``vorlage`` und gibt die erzeugten Schlüssel zurück."""
    erzeugt = []
    zeilen = []
    for zeile in vorlage.read_text(encoding="utf-8").splitlines():
        treffer = _ZEILE.match(zeile)
        if treffer and ERZEUGT.search(treffer.group(1)) and treffer.group(2).startswith(PLATZHALTER):
            zeile = f"{treffer.group(1)}={zufall()}"
            erzeugt.append(treffer.group(1))
        zeilen.append(zeile)
    _schreibe(ziel, "\n".join(zeilen) + "\n")
    return erzeugt


def offene_werte(ordner: Path) -> List[str]:
    """``datei: SCHLÜSSEL`` für jede Zuweisung, deren Wert noch ``change-me`` enthält."""
    offen = []
    for datei in sorted(ordner.glob(".env*")):
        if datei.name.endswith(".example"):
            continue
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            treffer = _ZEILE.match(zeile)
            if treffer and PLATZHALTER in treffer.group(2):
                offen.append(f"{datei.name}: {treffer.group(1)}")
    return offen


def starterpaket(wurzel: Path, ordner: Path, variante: Optional[str]) -> List[str]:
    """Stellt ``einstellungen/paperless/starterpaket/`` zusammen: ``basis`` plus
    die Ergänzungen der Variante. Ein Name in beiden ist ein Abbruch, weil
    ``apply.sh`` jeden Namen nur einmal anlegt."""
    pakete = wurzel / "starterpakete"
    basis = pakete / "basis"
    zusatz = None
    if variante:
        zusatz = pakete / variante
        if variante == "basis" or not zusatz.is_dir():
            vorhanden = sorted(p.name for p in pakete.iterdir() if p.is_dir() and p.name != "basis")
            raise Abbruch(f"Variante {variante!r} gibt es nicht. Vorhanden: {', '.join(vorhanden)}")
    ziel = ordner / "einstellungen" / "paperless" / "starterpaket"
    ziel.mkdir(parents=True, exist_ok=True)
    zeilen = []
    for name in STARTERPAKET:
        quelle = basis / f"{name}.json"
        if not quelle.is_file():
            continue
        ergaenzung = zusatz / f"{name}.json" if zusatz else None
        if ergaenzung is None or not ergaenzung.is_file():
            shutil.copyfile(quelle, ziel / f"{name}.json")
            continue
        eintraege = json.loads(quelle.read_text(encoding="utf-8"))
        dazu = json.loads(ergaenzung.read_text(encoding="utf-8"))
        namen = [e["name"] for e in eintraege + dazu if "name" in e]
        doppelt = sorted({n for n in namen if namen.count(n) > 1})
        if doppelt:
            raise Abbruch(f"{name}: in basis UND {variante}: {', '.join(doppelt)}")
        _schreibe(ziel / f"{name}.json", json.dumps(eintraege + dazu, ensure_ascii=False, indent=2) + "\n")
        zeilen.append(f"{name}.json: basis + {variante}")
    return zeilen


def anlegen(wurzel: Path, repo: Optional[str] = None, projekt: Optional[str] = None,
            variante: Optional[str] = None,
            zufall: Callable[[], str] = lambda: secrets.token_urlsafe(24)) -> List[str]:
    """Legt ``config/`` an, mit ``repo`` stattdessen
    ``config-repos/paper-werk-config-<repo>``, und gibt den Bericht zurück."""
    vorlage = wurzel / "config-template"
    if not vorlage.is_dir():
        raise Abbruch(f"Vorlage fehlt: {vorlage}")
    ziel = wurzel / REPOS / f"{PRAEFIX}{repo}" if repo else wurzel / KONFIG
    if ziel.exists():
        raise Abbruch(f"{ziel.relative_to(wurzel).as_posix()}/ gibt es schon; init überschreibt nichts.")
    projekt = projekt or (f"paper-werk-{repo}" if repo else PROJEKT_KONFIG)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", projekt):
        raise Abbruch(f"Projektname {projekt!r}: nur Kleinbuchstaben, Ziffern, - und _")

    shutil.copytree(vorlage, ziel)
    bericht = [f"Angelegt: {ziel.relative_to(wurzel).as_posix()}/ (Projekt {projekt})"]

    conf = ziel / "instanz.conf"
    _schreibe(conf, re.sub(r"(?m)^PROJEKT=.*$", f"PROJEKT={projekt}", conf.read_text(encoding="utf-8")))

    erzeugt = []
    for beispiel in sorted(ziel.glob(".env*.example")):
        erzeugt += _env_aus_vorlage(beispiel, ziel / beispiel.name[: -len(".example")], zufall)
        beispiel.unlink()
    bericht.append(f"Erzeugt: {', '.join(erzeugt)}")

    einstellungen = ziel / "einstellungen"
    for relativ in ("setup.conf", "n8n/config.json", "n8n/workflows.list"):
        beispiel = einstellungen / f"{relativ}.example"
        if beispiel.is_file():
            text = beispiel.read_text(encoding="utf-8").replace(f"{BEISPIEL_PROJEKT}-", f"{projekt}-")
            if relativ == "setup.conf":
                text = text.replace('APP_ADMIN_PASSWORD=""', f'APP_ADMIN_PASSWORD="{zufall()}"')
            _schreibe(einstellungen / relativ, text)
            beispiel.unlink()

    bericht += starterpaket(wurzel, ziel, variante)
    bericht.append(f"Starterpaket: basis{' + ' + variante if variante else ''}")

    offen = offene_werte(ziel)
    if offen:
        bericht.append("Noch auszufüllen:")
        bericht += [f"  {o}" for o in offen]
    name = f" {repo}" if repo else ""
    bericht += [
        "Außerdem: Hostname und Zugänge in einstellungen/setup.conf; KOPIA_PASSWORD gehört",
        "zusätzlich in den Passwortsafe, ohne ihn ist keine Sicherung lesbar.",
        f"Danach: paper-werk up{name}, dann paper-werk setup{name}.",
    ]
    return bericht
