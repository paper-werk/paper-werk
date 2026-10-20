"""``paper-werk init`` gegen ein nachgebautes Repo."""

import json
import re

import pytest

from conftest import schreibe
from paperwerk.ausgabe import Abbruch
from paperwerk.init import anlegen
from paperwerk.installation import finde


@pytest.fixture
def vorlage(repo):
    t = repo / "config-template"
    schreibe(t / "instanz.conf", "# Kopf\nPROJEKT=paper-werk\nHTTPS=nein\n")
    schreibe(t / ".gitignore", ".env*\n")
    schreibe(t / ".env.example", "# Kommentar\nPOSTGRES_PASSWORD=change-me\nPAPER_WERK_DATA_ROOT=/home/change-me/pw\n")
    schreibe(t / ".env.app.example", "DJANGO_SECRET_KEY=change-me\nDJANGO_ALLOWED_HOSTS=localhost,change-me\n")
    schreibe(t / ".env.paperless.example", "PAPERLESS_AI_LLM_API_KEY=change-me\n")
    schreibe(t / "einstellungen" / "setup.conf.example",
             'APP_CONTAINER="kunde-xyz-paper-werk-app-1"\nAPP_ADMIN_PASSWORD=""\n')
    schreibe(t / "einstellungen" / "n8n" / "workflows.list.example", "a.json\n")
    b = repo / "starterpakete" / "basis"
    schreibe(b / "tags.json", json.dumps([{"_kommentar": "k"}, {"name": "Rechnung"}]))
    schreibe(b / "document_types.json", json.dumps([{"name": "Angebot"}]))
    schreibe(repo / "starterpakete" / "elektro" / "tags.json", json.dumps([{"name": "Baustelle"}]))
    return t


def test_config_mit_erzeugten_kennwoertern(repo, vorlage):
    werte = iter(f"geheim{i}" for i in range(10))
    bericht = anlegen(repo, zufall=lambda: next(werte))
    c = repo / "config"
    assert re.fullmatch(r"# Kommentar\nPOSTGRES_PASSWORD=geheim\d\nPAPER_WERK_DATA_ROOT=/home/change-me/pw\n",
                        (c / ".env").read_text(encoding="utf-8"))
    assert "DJANGO_SECRET_KEY=geheim" in (c / ".env.app").read_text(encoding="utf-8")
    assert not list(c.glob(".env*.example"))
    assert (c / "einstellungen" / "setup.conf").read_text(encoding="utf-8").startswith(
        'APP_CONTAINER="paper-werk-paper-werk-app-1"\nAPP_ADMIN_PASSWORD="geheim')
    assert (c / "einstellungen" / "n8n" / "workflows.list").is_file()
    assert (c / "einstellungen" / "paperless" / "starterpaket" / "tags.json").is_file()
    offen = [z.strip() for z in bericht if ": " in z and z.startswith("  ")]
    assert offen == [".env: PAPER_WERK_DATA_ROOT", ".env.app: DJANGO_ALLOWED_HOSTS",
                     ".env.paperless: PAPERLESS_AI_LLM_API_KEY"]
    assert finde(repo, "").projekt == "paper-werk"


def test_repo_mit_variante_und_projektname(repo, vorlage):
    anlegen(repo, repo="kunde", variante="elektro")
    inst = finde(repo, "kunde")
    assert inst.ordner == repo / "config-repos" / "paper-werk-config-kunde"
    assert inst.projekt == "paper-werk-kunde"
    tags = json.loads((inst.ordner / "einstellungen" / "paperless" / "starterpaket" / "tags.json")
                      .read_text(encoding="utf-8"))
    assert [t.get("name") for t in tags] == [None, "Rechnung", "Baustelle"]


def test_ueberschreibt_nie(repo, vorlage):
    (repo / "config").mkdir()
    with pytest.raises(Abbruch, match="gibt es schon"):
        anlegen(repo)


def test_doppelter_name_in_variante(repo, vorlage):
    schreibe(repo / "starterpakete" / "elektro" / "document_types.json", '[{"name": "Angebot"}]')
    with pytest.raises(Abbruch, match="Angebot"):
        anlegen(repo, variante="elektro")


def test_unbekannte_variante(repo, vorlage):
    with pytest.raises(Abbruch, match="Vorhanden: elektro"):
        anlegen(repo, variante="dach")
