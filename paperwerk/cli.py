"""Befehle von ``./paper-werk``.

Unterbefehle heißen wie bei docker compose, wo es ein Gegenstück gibt
(``up``, ``stop``, ``down``), sonst englisch (``init``, ``list``, ``switch``,
``doctor``, ``env-check``, ``setup``, ``update``, ``migrate-volumes``,
``command``).

Ohne Namen gilt ``config/``, die Installation des Rechners. Ein Name wählt
``config-repos/paper-werk-config-<name>``. Bei Befehlen, die Argumente an
docker compose weiterreichen, ist das erste Wort der Name, wenn es eine
Installation dieses Namens gibt (``up dev --build`` gegenüber ``up --build``).
``setup`` und ``update`` rufen bis zu ihrer Portierung die
Shell-Skripte unter ``setup/`` auf, damit die CLI schon jetzt der eine
Einstieg ist. Die Shell-Skripte bleiben bis dahin gültig und unverändert.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from paperwerk import docker
from paperwerk.ausgabe import GRUEN, Abbruch, faerben, fehler, meld, utf8_ausgabe
from paperwerk.doktor import doktor
from paperwerk.env_abgleich import abgleichen, bericht
from paperwerk.init import anlegen
from paperwerk.installation import finde, installationen, ist_installation
from paperwerk.volumes import umziehen

WURZEL = Path(__file__).resolve().parent.parent


def _liste(wurzel: Path) -> List[str]:
    zeilen = []
    for inst in installationen(wurzel):
        art = "Vorlage" if inst.neuer_aufbau else "eigene Kopie (alter Aufbau)"
        if not inst.hat_env:
            art += ", ohne .env"
        art += f", {inst.ordner.relative_to(wurzel).as_posix()}"
        if docker.laeuft(inst.projekt):
            zeilen.append(f"  {faerben('●', GRUEN)} {inst.anzeigename:<18} {art} (läuft)")
        else:
            zeilen.append(f"  ○ {inst.anzeigename:<18} {art}")
    return zeilen


def befehl_liste(wurzel: Path, args) -> int:
    print("\n".join(_liste(wurzel)))
    return 0


def _name_und_rest(wurzel: Path, woerter: List[str]):
    """Trennt einen führenden Installationsnamen von den übrigen Wörtern."""
    if woerter and ist_installation(wurzel, woerter[0]):
        return woerter[0], list(woerter[1:])
    return "", list(woerter)


def _compose(wurzel: Path, args, vorne: List[str]) -> int:
    name, rest = _name_und_rest(wurzel, args.rest)
    return docker.compose(finde(wurzel, name), [*vorne, *rest])


def befehl_hoch(wurzel: Path, args) -> int:
    return _compose(wurzel, args, ["up", "-d"])


def befehl_stop(wurzel: Path, args) -> int:
    return _compose(wurzel, args, ["stop"])


def befehl_runter(wurzel: Path, args) -> int:
    return _compose(wurzel, args, ["down"])


def befehl_compose(wurzel: Path, args) -> int:
    name, rest = _name_und_rest(wurzel, args.rest)
    if not rest:
        raise Abbruch("Was soll docker compose tun? Zum Beispiel: logs -f paperless")
    return docker.compose(finde(wurzel, name), rest)


def befehl_befehl(wurzel: Path, args) -> int:
    inst = finde(wurzel, args.name)
    umgebung = " ".join(f"{k}={shlex.quote(v)}" for k, v in inst.compose_umgebung().items())
    aufruf = " ".join(shlex.quote(t) for t in inst.compose_befehl())
    print(f"{umgebung} {aufruf}" if umgebung else aufruf)
    return 0


def befehl_umschalten(wurzel: Path, args) -> int:
    """Stoppt alle anderen Installationen (``compose stop``: Container und Daten
    bleiben) und startet die genannte. Die Installationen teilen sich die
    Host-Ports, es läuft immer nur eine."""
    kandidaten = [i for i in installationen(wurzel, mit_konfig=False) if i.hat_env]
    if not args.name:
        for inst in kandidaten:
            an = docker.laeuft(inst.projekt)
            print(f"  {faerben('●', GRUEN)} {inst.name} (läuft)" if an else f"  ○ {inst.name}")
        return 0
    ziel = next((i for i in kandidaten if i.name == args.name), None)
    if ziel is None:
        raise Abbruch(f"Keine Installation mit .env: {args.name} "
                      f"(vorhanden: {', '.join(i.name for i in kandidaten)})")
    for inst in kandidaten:
        if inst is not ziel and docker.laeuft(inst.projekt):
            meld(inst.name, "stop")
            code = docker.compose(inst, ["stop"])
            if code:
                return code
    meld(ziel.name, "start")
    code = docker.compose(ziel, ["up", "-d"])
    if code == 0:
        print(f"\n{faerben(ziel.name + ' läuft.', GRUEN)}  Eingang: http://localhost/")
    return code


def befehl_doktor(wurzel: Path, args) -> int:
    print("\n".join(doktor(finde(wurzel, args.name))))
    return 0


def befehl_env_abgleich(wurzel: Path, args) -> int:
    inst = finde(wurzel, args.name)
    print("\n".join(bericht(abgleichen(wurzel / "config-template", inst.ordner))))
    return 0


def bash_programm() -> str:
    """Bash für die noch nicht portierten Skripte. Unter Windows die Git Bash:
    ``bash`` im PATH ist dort oft ``System32\\bash.exe`` (WSL), das die
    Docker-Desktop-Pfade nicht kennt."""
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for kandidat in (Path(git).parent.parent / "bin" / "bash.exe",
                             Path(git).parent / "bash.exe"):
                if kandidat.is_file():
                    return str(kandidat)
    bash = shutil.which("bash")
    if not bash:
        raise Abbruch("bash nicht gefunden; unter Windows Git for Windows installieren")
    return bash


def _shell(wurzel: Path, skript: str, *argumente: str) -> int:
    befehl = [bash_programm(), str(wurzel / skript), *argumente]
    return subprocess.run(befehl, cwd=str(wurzel)).returncode


def befehl_einrichten(wurzel: Path, args) -> int:
    name, module = _name_und_rest(wurzel, args.woerter)
    inst = finde(wurzel, name)
    zusatz = ["--force"] if args.force else []
    # setup.sh wechselt nach setup/ und löst --project von dort auf.
    projekt = os.path.relpath(inst.ordner, wurzel / "setup").replace(os.sep, "/")
    return _shell(wurzel, "setup/setup.sh", "--project", projekt, *module, *zusatz)


def befehl_aktualisieren(wurzel: Path, args) -> int:
    inst = finde(wurzel, args.name)
    zusatz = [f"--{o}" for o, an in (("ohne-sicherung", args.ohne_sicherung),
                                      ("mit-setup", args.mit_setup),
                                      ("trocken", args.trocken)) if an]
    return _shell(wurzel, "setup/aktualisieren.sh", *([inst.name] if inst.name else []), *zusatz)


def befehl_volumes_umziehen(wurzel: Path, args) -> int:
    print("\n".join(umziehen(finde(wurzel, args.name), docker.compose, trocken=args.trocken)))
    return 0


def befehl_init(wurzel: Path, args) -> int:
    print("\n".join(anlegen(wurzel, repo=args.repo, projekt=args.projekt, variante=args.variante)))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paper-werk",
        description="Installationen anlegen, starten, prüfen und pflegen. "
                    "Ohne Namen gilt config/, mit Namen config-repos/paper-werk-config-<name>.",
        epilog="Ohne Befehl: Liste der Installationen. Hilfe zu einem Befehl: paper-werk <befehl> -h",
    )
    befehle = p.add_subparsers(dest="befehl", metavar="<befehl>")

    def neu(name, funktion, hilfe, mit_name=True, rest=False):
        b = befehle.add_parser(name, help=hilfe, description=hilfe)
        if rest:
            b.add_argument("rest", nargs=argparse.REMAINDER, metavar="[name] ...",
                           help="Installation (ohne Angabe: config/), danach Argumente für docker compose")
        elif mit_name:
            b.add_argument("name", nargs="?", default="",
                           help="Installation unter config-repos/; ohne Angabe: config/")
        b.set_defaults(funktion=funktion)
        return b

    i = neu("init", befehl_init, "neue Installation aus config-template/ anlegen", mit_name=False)
    i.add_argument("--repo", metavar="NAME",
                   help="unter config-repos/paper-werk-config-NAME statt in config/")
    i.add_argument("--projekt", metavar="NAME",
                   help="Compose-Projektname, Präfix der Container; Vorgabe paper-werk bzw. paper-werk-NAME")
    i.add_argument("--variante", metavar="NAME", help="Starterpaket-Variante, z. B. elektro")
    neu("list", befehl_liste, "Installationen und was läuft", mit_name=False)
    neu("up", befehl_hoch, "Installation starten (docker compose up -d)", rest=True)
    neu("stop", befehl_stop, "Installation anhalten, Container bleiben (docker compose stop)", rest=True)
    neu("down", befehl_runter, "Container entfernen, Daten bleiben (docker compose down)", rest=True)
    neu("compose", befehl_compose, "beliebiger docker-compose-Befehl, z. B. logs -f paperless", rest=True)
    neu("command", befehl_befehl, "nur den docker-compose-Aufruf zeigen")
    u = neu("switch", befehl_umschalten, "alle anderen anhalten, diese starten", mit_name=False)
    u.add_argument("name", nargs="?", help="Installation; ohne Angabe: was läuft")
    neu("doctor", befehl_doktor, "Zustandsbericht, ändert nichts")
    neu("env-check", befehl_env_abgleich, ".env-Dateien mit den Vorlagen vergleichen")

    e = neu("setup", befehl_einrichten,
            "Starterpaket einspielen (vorerst über setup/setup.sh)", mit_name=False)
    e.add_argument("woerter", nargs="*", metavar="[name] modul",
                   help="Installation (ohne Angabe: config/), dann app, paperless, n8n, kopia, sso; "
                        "ohne Modul: app paperless n8n kopia")
    e.add_argument("--force", action="store_true", help="vorhandene n8n-Workflows überschreiben")

    v = neu("migrate-volumes", befehl_volumes_umziehen,
            "Bind-Ordner (alter Aufbau) in benannte Volumes kopieren; die Ordner bleiben")
    v.add_argument("--trocken", action="store_true", help="nur zeigen, was umzieht")

    a = neu("update", befehl_aktualisieren,
            "sichern, neuen Stand holen, bauen, starten (vorerst über setup/aktualisieren.sh)")
    a.add_argument("--ohne-sicherung", action="store_true", help="nur für Testinstallationen")
    a.add_argument("--mit-setup", action="store_true", help="Starterpaket erneut einspielen")
    a.add_argument("--trocken", action="store_true", help="nur zeigen, was geschähe")
    return p


def main(argv: Optional[List[str]] = None, wurzel: Path = WURZEL) -> int:
    utf8_ausgabe()
    p = parser()
    args, unbekannt = p.parse_known_args(argv)
    # REMAINDER nimmt führende Optionen nicht auf: "up --build" landet hier.
    # Bei Befehlen, die an docker compose weiterreichen, gehören sie dazu.
    if unbekannt:
        if not hasattr(args, "rest"):
            p.error(f"unbekannte Argumente: {' '.join(unbekannt)}")
        args.rest = unbekannt + args.rest
    funktion = getattr(args, "funktion", befehl_liste)
    try:
        return funktion(wurzel, args) or 0
    except Abbruch as abbruch:
        fehler(str(abbruch))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
