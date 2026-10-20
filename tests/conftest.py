"""Gemeinsame Fixtures: ein nachgebautes Install-Repo in ``tmp_path``, ohne Docker."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def schreibe(pfad: Path, text: str = "") -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")
    return pfad


@pytest.fixture
def repo(tmp_path):
    """Install-Repo mit Vorlage und Nachbar-Repo paper-werk-app."""
    wurzel = tmp_path / "paper-werk"
    schreibe(wurzel / "compose" / "docker-compose.yml", "services: {}\n")
    schreibe(wurzel / "compose" / "compose.https.yml", "services: {}\n")
    (wurzel / "compose" / "caddy").mkdir()
    schreibe(tmp_path / "paper-werk-app" / "Dockerfile")
    return wurzel


@pytest.fixture
def kein_docker(monkeypatch):
    """Ersetzt die Docker-Abfragen; ``laufend`` nimmt Compose-Projektnamen auf."""
    from paperwerk import docker

    laufend = set()
    aufrufe = []
    monkeypatch.setattr(docker, "container",
                        lambda projekt, alle=False: [(projekt + "-x-1", "Up 1 hour")] if projekt in laufend else [])

    def compose(inst, argumente, env_pflicht=True):
        aufrufe.append((inst.anzeigename, list(argumente)))
        return 0

    monkeypatch.setattr(docker, "compose", compose)
    return laufend, aufrufe
