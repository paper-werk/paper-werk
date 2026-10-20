"""Abgleich der .env-Schlüssel mit den Vorlagen; Werte zählen nie."""

import pytest

from conftest import schreibe
from paperwerk.ausgabe import Abbruch
from paperwerk.env_abgleich import Abgleich, abgleichen, bericht


def test_pflicht_und_angebot(tmp_path):
    vorlagen, projekt = tmp_path / "template", tmp_path / "projekt"
    schreibe(vorlagen / ".env.example", "A=1\nB=2\n# C=3\n#D=4\n#  kein Schlüssel\n")
    schreibe(vorlagen / ".env.app.example", "X=1\n")
    schreibe(projekt / ".env", "A=anders\nD=da\n")

    assert abgleichen(vorlagen, projekt) == [
        Abgleich(".env.app", False, [], []),
        Abgleich(".env", True, ["B"], ["C"]),
    ]


def test_bericht_zaehlt_fehlende(tmp_path):
    zeilen = bericht([Abgleich(".env", True, ["B", "E"], []), Abgleich(".env.kopia", True, [], [])])
    assert zeilen[:3] == [".env", "  fehlt:   B", "  fehlt:   E"]
    assert ".env.kopia: vollständig" in zeilen
    assert zeilen[-1].startswith("2 Schlüssel fehlen")


def test_bericht_ohne_env_bricht_ab():
    with pytest.raises(Abbruch):
        bericht([Abgleich(".env", False, [], [])])
