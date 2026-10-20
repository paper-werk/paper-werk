"""Befehle der CLI gegen ein nachgebautes Repo; Docker ist ersetzt."""

from conftest import schreibe
from paperwerk.cli import main


def _installation(repo, name, conf="", env=True):
    ordner = repo / "config-repos" / f"paper-werk-config-{name}"
    schreibe(ordner / "instanz.conf", conf)
    if env:
        schreibe(ordner / ".env", "")
    return ordner


def test_liste_fragt_nach_projektname_nicht_ordnername(repo, kein_docker, capsys):
    """stack.sh fragte mit dem Ordnernamen; kunde läuft als paper-werk-kunde und
    erschien dort nie als laufend."""
    laufend, _ = kein_docker
    _installation(repo, "kunde", "PROJEKT=paper-werk-kunde\n")
    _installation(repo, "test", env=False)
    laufend.add("paper-werk-kunde")

    assert main([], wurzel=repo) == 0
    zeilen = capsys.readouterr().out.splitlines()
    assert "kunde" in zeilen[0] and "(läuft)" in zeilen[0]
    assert "test" in zeilen[1] and "ohne .env" in zeilen[1]


def test_up_stop_down_und_durchreichen(repo, kein_docker):
    _, aufrufe = kein_docker
    _installation(repo, "kunde")
    main(["up", "kunde", "--build"], wurzel=repo)
    main(["stop", "kunde"], wurzel=repo)
    main(["down", "kunde"], wurzel=repo)
    main(["compose", "kunde", "logs", "-f", "paperless"], wurzel=repo)
    assert aufrufe == [
        ("kunde", ["up", "-d", "--build"]),
        ("kunde", ["stop"]),
        ("kunde", ["down"]),
        ("kunde", ["logs", "-f", "paperless"]),
    ]


def test_unbekannte_installation(repo, kein_docker, capsys):
    """Ein unbekanntes erstes Wort ist kein Name, sondern ein Argument für
    config/; ohne config/ bricht das ab."""
    assert main(["up", "gibtsnicht"], wurzel=repo) == 1
    assert "Kein config/" in capsys.readouterr().err
    assert main(["doctor", "gibtsnicht"], wurzel=repo) == 1
    assert "Keine Installation: gibtsnicht" in capsys.readouterr().err


def test_ohne_namen_gilt_config(repo, kein_docker):
    _, aufrufe = kein_docker
    schreibe(repo / "config" / "instanz.conf", "")
    schreibe(repo / "config" / ".env", "")
    _installation(repo, "dev")
    main(["up", "--build"], wurzel=repo)
    main(["up", "dev"], wurzel=repo)
    main(["compose", "logs", "-f"], wurzel=repo)
    assert aufrufe == [
        ("config", ["up", "-d", "--build"]),
        ("dev", ["up", "-d"]),
        ("config", ["logs", "-f"]),
    ]


def test_switch_ignoriert_config(repo, kein_docker):
    laufend, aufrufe = kein_docker
    schreibe(repo / "config" / "instanz.conf", "PROJEKT=pw-config\n")
    schreibe(repo / "config" / ".env", "")
    _installation(repo, "b")
    laufend.add("pw-config")
    assert main(["switch", "b"], wurzel=repo) == 0
    assert aufrufe == [("b", ["up", "-d"])]


def test_switch_stoppt_andere_und_startet_ziel(repo, kein_docker):
    laufend, aufrufe = kein_docker
    _installation(repo, "a", "PROJEKT=pw-a\n")
    _installation(repo, "b")
    _installation(repo, "ohne-env", env=False)
    laufend.add("pw-a")

    assert main(["switch", "b"], wurzel=repo) == 0
    assert aufrufe == [("a", ["stop"]), ("b", ["up", "-d"])]


def test_command_zeigt_aufruf_ohne_env(repo, kein_docker, capsys):
    _installation(repo, "x", "PROJEKT=pw-x\n", env=False)
    assert main(["command", "x"], wurzel=repo) == 0
    ausgabe = capsys.readouterr().out
    assert "docker compose -f" in ausgabe and ausgabe.rstrip().endswith("-p pw-x")
    assert "PAPER_WERK_CADDY_DIR=" in ausgabe
