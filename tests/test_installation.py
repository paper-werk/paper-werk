"""Auflösung einer Installation zu ihrem ``docker compose``-Aufruf; muss ``stack.sh`` entsprechen."""

import pytest

from conftest import schreibe
from paperwerk.ausgabe import Abbruch
from paperwerk.installation import Installation, finde, hostpfad, installationen, lies_zuweisungen


def test_zuweisungen_mit_anfuehrung_und_kommentar(tmp_path):
    datei = schreibe(tmp_path / "instanz.conf",
                     "# Kopf\n\nPROJEKT=paper-werk-kunde\nHTTPS=ja  # wegen Entra\n"
                     'ZUSATZ="a.yml b.yml"\nPROFILE=\'\'\nexport X=1\r\n')
    assert lies_zuweisungen(datei, streng=True) == {
        "PROJEKT": "paper-werk-kunde", "HTTPS": "ja", "ZUSATZ": "a.yml b.yml", "PROFILE": "", "X": "1",
    }


def test_streng_lehnt_shell_code_ab(tmp_path):
    datei = schreibe(tmp_path / "instanz.conf", "PROJEKT=x\nif true; then HTTPS=ja; fi\n")
    with pytest.raises(Abbruch, match="instanz.conf:2"):
        lies_zuweisungen(datei, streng=True)
    assert lies_zuweisungen(datei) == {"PROJEKT": "x"}


def test_vorgaben_ohne_eintraege(repo):
    schreibe(repo / "config-repos" / "paper-werk-config-demo" / "instanz.conf", "# leer\n")
    inst = Installation(repo, "demo")
    assert inst.projekt == "demo"
    assert not inst.https
    assert inst.compose_dateien() == [repo / "compose" / "docker-compose.yml"]


def test_reihenfolge_der_compose_dateien(repo):
    ordner = repo / "config-repos" / "paper-werk-config-kunde"
    schreibe(ordner / "instanz.conf",
             'PROJEKT=paper-werk-kunde\nHTTPS=ja\nZUSATZ="compose.zusatz.yml"\nPROFILE="werkzeuge kopia"\n')
    schreibe(ordner / "compose.zusatz.yml")
    schreibe(ordner / "compose.override.yml")
    inst = Installation(repo, "kunde")

    assert inst.compose_dateien() == [
        repo / "compose" / "docker-compose.yml",
        repo / "compose" / "compose.https.yml",
        ordner / "compose.zusatz.yml",
        ordner / "compose.override.yml",
    ]
    befehl = inst.compose_befehl()
    assert befehl[-6:] == ["--profile", "kopia", "--project-directory", hostpfad(ordner), "-p", "paper-werk-kunde"]
    assert befehl[befehl.index("--profile") + 1] == "werkzeuge"


def test_fehlende_zusatzdatei_bricht_ab(repo):
    schreibe(repo / "config-repos" / "paper-werk-config-x" / "instanz.conf", "ZUSATZ=fehlt.yml\n")
    with pytest.raises(Abbruch, match="fehlt.yml"):
        Installation(repo, "x").compose_befehl()


def test_umgebung_vorgaben(repo):
    schreibe(repo / "config-repos" / "paper-werk-config-x" / "instanz.conf", "")
    umgebung = Installation(repo, "x").compose_umgebung()
    assert umgebung == {
        "PAPER_WERK_CADDY_DIR": hostpfad(repo / "compose" / "caddy"),
        "PAPER_WERK_APP_CONTEXT": hostpfad(repo.parent / "paper-werk-app"),
    }


def test_umgebung_eigener_caddy_ordner_und_env_hat_vorrang(repo):
    ordner = repo / "config-repos" / "paper-werk-config-x"
    schreibe(ordner / "instanz.conf", "")
    (ordner / "caddy").mkdir()
    assert Installation(repo, "x").compose_umgebung()["PAPER_WERK_CADDY_DIR"] == hostpfad(ordner / "caddy")

    schreibe(ordner / ".env", "  PAPER_WERK_APP_CONTEXT=/woanders\nPAPER_WERK_CADDY_DIR=/c\n")
    assert Installation(repo, "x").compose_umgebung() == {}


def test_alter_aufbau(repo):
    ordner = repo / "config-repos" / "paper-werk-config-alt"
    schreibe(ordner / "docker-compose.yml")
    inst = Installation(repo, "alt")
    assert not inst.neuer_aufbau
    assert inst.compose_befehl() == [
        "docker", "compose", "-f", hostpfad(ordner / "docker-compose.yml"),
        "--project-directory", hostpfad(ordner), "-p", "alt",
    ]
    assert inst.compose_umgebung() == {}


def test_installationen_ohne_archiv_und_ohne_leere_ordner(repo):
    schreibe(repo / "config-repos" / "paper-werk-config-b" / "instanz.conf")
    schreibe(repo / "config-repos" / "paper-werk-config-a" / "docker-compose.yml")
    schreibe(repo / "config-repos" / "paper-werk-config-archiv" / "alt" / "docker-compose.yml")
    (repo / "config-repos" / "paper-werk-config-leer").mkdir()
    assert [i.name for i in installationen(repo)] == ["a", "b"]


def test_finde_unbekannt_nennt_vorhandene(repo):
    schreibe(repo / "config-repos" / "paper-werk-config-kunde" / "instanz.conf")
    with pytest.raises(Abbruch, match=r"Keine Installation: xyz \(vorhanden: kunde\)"):
        finde(repo, "xyz")
