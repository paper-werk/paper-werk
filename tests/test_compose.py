"""Die ausgelieferte Compose-Vorlage: Kopia sichert jedes Volume.

Gegen die echte Datei in compose/, nicht gegen eine nachgebaute.
"""

import re
from pathlib import Path

from paperwerk.volumes import alter_ordner, volumes_der_vorlage

WURZEL = Path(__file__).resolve().parent.parent

#: Bewusst nicht gesichert: Redis ist Warteschlange und Cache, Kopia sichert
#: sich nicht selbst.
NICHT_GESICHERT = {"redisdata", "kopia-config", "kopia-cache", "kopia-repository"}


def _kopia_mounts(ziel: str):
    text = (WURZEL / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    return re.findall(rf"(?m)^      - ([a-z0-9-]+):/{ziel}/paper-werk/([a-z0-9-]+)", text)


def test_jedes_volume_ist_gesichert_oder_ausdruecklich_ausgenommen():
    volumes = set(volumes_der_vorlage(WURZEL))
    gesichert = {quelle for quelle, _ in _kopia_mounts("source")}
    assert volumes - NICHT_GESICHERT == gesichert
    assert NICHT_GESICHERT <= volumes


def test_restore_ziel_fuer_jedes_gesicherte_volume():
    assert {q for q, _ in _kopia_mounts("restore")} == {q for q, _ in _kopia_mounts("source")}


def test_ordner_in_der_quelle_heisst_wie_das_volume():
    """Die Ausschlussregeln (ignore.rules, etwa /data/index) und alte Snapshots
    adressieren die Ordner unter /source/paper-werk mit dem Volume-Namen."""
    for quelle, ordner in _kopia_mounts("source") + _kopia_mounts("restore"):
        assert quelle == ordner


def test_alter_ordner():
    assert alter_ordner("pgdata", "/opt/pw/daten/", "/opt/pw/kopia") == "/opt/pw/daten/pgdata"
    assert alter_ordner("kopia-cache", "/opt/pw/daten", "/opt/pw/kopia") == "/opt/pw/kopia/cache"


def test_snapshot_zeit_aus_kopia():
    from paperwerk.doktor import snapshot_zeit

    assert snapshot_zeit("2026-10-17T21:00:03.556012603Z") == snapshot_zeit("2026-10-17T23:00:03+02:00")
    assert snapshot_zeit("2026-10-17T21:00:03Z") - snapshot_zeit("2026-10-17T20:00:03Z") == 3600
    assert snapshot_zeit("kaputt") is None
