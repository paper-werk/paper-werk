# config/ und config-repos/

Die Konfiguration einer Installation liegt nicht in diesem Repo. Es gibt
zwei Orte, beide ignoriert (bis auf diese Datei):

```
paper-werk/
├── config/                          die Installation dieses Rechners
└── config-repos/                    mehrere Installationen (Entwicklung)
    ├── README.md
    ├── paper-werk-config-dev/       "dev": Entwicklung
    ├── paper-werk-config-lasttest/  "lasttest": Prüfstand
    ├── paper-werk-config-kunde/     "kunde"
    └── paper-werk-config-archiv/    Ablage alter Installationen, keine Installation
```

**config/** ist der Normalfall: Ein Kunde hat eine Installation. Alle Befehle
kommen ohne Namen aus: `./paper-werk up`, `./paper-werk doctor`,
`./paper-werk update`. `config/` ist ein einfacher Ordner oder ein
geklontes Config-Repo; liegt darin ein `.git`, holt `./paper-werk update` es mit.

**config-repos/** ist für einen Rechner mit mehreren Installationen. Jede ist
ein privates Repo `paper-werk-config-<name>`, geklont unter demselben Namen.
Der Name der Installation ist der Teil hinter `paper-werk-config-`:
`./paper-werk up dev`, `./paper-werk doctor kunde`, `./paper-werk switch lasttest`.

Die Auflösung steht in `setup/lib/installation.sh`. Ist das erste Argument
der Name einer Installation, gilt diese, sonst `config/`. Für ältere Installationen gilt als Rückfall noch `projekte/paper-werk-config-<name>`
und `projekte/<name>`; liegt ein Name an mehreren Orten, brechen die
Skripte ab.

Gültig ist ein Ordner mit `instanz.conf` (oder, alter Aufbau,
`docker-compose.yml`).

Grund für eigene Repos: Das Install-Repo liegt bei jedem Kunden auf dem
Server. Lägen die Installationen darin, sähe jeder Kunde die Konfiguration
der anderen, auch in der Historie. So bekommt ein Server nur Lesezugriff auf
sein eigenes Repo.

In VS Code und Git gilt: Änderungen in `config/` oder
`config-repos/paper-werk-config-*` werden dort committet und gepusht, nicht
in diesem Repo.

## Relative Pfade

Compose-Zusätze und `ZUSATZREPOS` in `instanz.conf` gelten vom
Installationsordner aus. `config/` liegt eine Ebene weniger tief als
`config-repos/paper-werk-config-<name>`:

| | Vorlage | Nachbar-Repo (etwa paper-werk-zusatz) |
| --- | --- | --- |
| `config/` | `../compose` | `../../paper-werk-zusatz` |
| `config-repos/paper-werk-config-<name>/` | `../../compose` | `../../../paper-werk-zusatz` |

Ein Config-Repo mit relativen Pfaden funktioniert deshalb nur an einem der
beiden Orte.

## Was in ein Config-Repo gehört

Versioniert: `instanz.conf`, eigene Compose-Zusätze (`ZUSATZ`),
`einstellungen/`, `caddy/` falls eigene Einstiegsseite, Doku zur
Installation.

Nie versioniert (`.gitignore` im Config-Repo): `.env*` außer `*.example`,
`zertifikate/`, `einstellungen/setup.conf`, `einstellungen/n8n/credentials.json`,
`notiz-*.md`. Gilt ein Config-Repo für mehrere Rechner, gehören Abweichungen eines
einzelnen in `compose.override.yml`, ebenfalls nicht versioniert.

`./paper-werk update` holt das Config-Repo mit (`git pull --ff-only`) und
bricht ab, wenn darin versionierte Dateien geändert sind.

## Neue Installation

```bash
git clone <url>/paper-werk-config-<name> config      # oder: cp -r config-template config
cd config
for v in .env*.example; do cp -n "$v" "${v%.example}"; done   # bei cp -r
```

`config-template/` bringt `instanz.conf`, `.gitignore`, `README.md`, die
`.env`-Vorlagen und `einstellungen/` mit. Bei einem geklonten Config-Repo
kommen die Vorlagen aus `../config-template/`.

Danach die `.env*` ausfüllen und weiter wie in `Kundeninstallation.md`.
Für einen weiteren Eintrag unter `config-repos/` dasselbe mit
`config-repos/paper-werk-config-<name>` und `../../config-template`.

## Umzug von projekte/ nach config-repos/

Ist `projekte/paper-werk-config-<name>` bereits ein Config-Repo, reicht

```bash
./paper-werk compose <name> config > ~/config-vorher.yml
mv projekte/paper-werk-config-<name> config-repos/
./paper-werk compose <name> config | diff ~/config-vorher.yml -   # nur Pfade
./paper-werk up <name>                                  # Bind-Mounts neu
```

Die Tiefe bleibt gleich, relative Pfade im Repo stimmen weiter. Unter
Windows schlägt `mv` fehl, solange eine Shell oder ein Editor im Ordner
steht. `up` erzeugt die Container neu, deren Bind-Mounts auf den alten
Ordner zeigten.
