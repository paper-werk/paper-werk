# Paper-Werk

Paper-Werk ist eine Projektabrechnung für Betriebe in Deutschland: Angebote,
Aufträge, Rechnungen und Mahnungen, Leistungserfassung und Controlling, mit
E-Rechnung nach EN 16931 (Factur-X, XRechnung). Die Anwendung selbst liegt in
[paper-werk-app](https://github.com/paper-werk/paper-werk-app).

Das Video zeigt in rund 1:40 Minuten den Weg vom Angebot bis zur bezahlten
Rechnung, mit Vorführdaten:


https://github.com/user-attachments/assets/10f5a2a4-6c86-4e36-b083-2a85bd9b3790


Dieses Repo installiert und betreibt Paper-Werk. Es startet die Anwendung
zusammen mit den Diensten, an die sie angebunden ist:

- [Paperless-ngx](https://docs.paperless-ngx.com/) als Archiv. Festgeschriebene
  Belege werden dort abgelegt, eingehende Rechnungen kommen von dort in die
  Projektabrechnung ([docs/belege-nach-paper-werk.md](docs/belege-nach-paper-werk.md)).
- [n8n](https://n8n.io/) für die Abläufe zwischen Archiv, Anwendung und
  Steuerberatung ([n8n/](n8n/)).
- [Kopia](https://kopia.io/) für die Datensicherung
  ([docs/kopia-backblaze.md](docs/kopia-backblaze.md)).
- [Caddy](https://caddyserver.com/) als Einstiegsseite und für HTTPS.

Dazu gehören die Kommandozeile `./paper-werk`, die Setup-Skripte, die
Paperless-Starterpakete und Demobestände zum Ausprobieren.

## Schnellstart

Voraussetzungen: Docker, Git (unter Windows Git for Windows mit Git Bash),
jq, Python ab 3.8.

```bash
git clone https://github.com/paper-werk/paper-werk.git
cd paper-werk
./paper-werk init      # legt config/ an, erzeugt Kennwörter
                       # und nennt, was noch auszufüllen ist
# offene Werte in config/.env* ausfüllen (Kundeninstallation.md, Schritt 4)
./paper-werk up        # Images laden und starten
# Paperless-Token in config/einstellungen/setup.conf und .env.app (Schritt 5)
./paper-werk setup     # Starterpaket in Paperless, n8n und Kopia
./paper-werk doctor    # Zustandsbericht
```

Die Anwendung kommt als fertiges Image (`ghcr.io/paper-werk/paper-werk-app`).
Hilfe zu allen
Befehlen: `./paper-werk -h`. Die ausführliche Anleitung mit HTTPS, Anmeldung
über Microsoft und Fehlerbildern steht in
[Kundeninstallation.md](Kundeninstallation.md); wo die Konfiguration liegt,
in [config-repos/README.md](config-repos/README.md).

## Struktur

| Pfad | Zweck |
| --- | --- |
| [compose/](compose/) | **Was gestartet wird**, für jede Installation dasselbe und nie kopiert: `docker-compose.yml`, das Zusatzstück `compose.https.yml` für HTTPS, `compose.build.yml` zum Bauen der App aus dem Quelltext (`APP_BAUEN=ja`) und [caddy/](compose/caddy/) (Einstiegsseite, http und https). |
| [config-template/](config-template/) | **Was in eine neue Installation kopiert wird**: `.env`-Vorlagen und [einstellungen/](config-template/einstellungen/) (die Werte für die Setup-Skripte: `setup.conf`, n8n-Liste, Kopia-Ignores), dazu `instanz.conf`, `.gitignore` und `README.md` für ein Config-Repo. Das Paperless-Starterpaket kommt aus [starterpakete/](starterpakete/). |
| [starterpakete/](starterpakete/) | Paperless-Starterpakete: `basis/` ist das Paket für alle, eine Variante wie `elektro/` enthält nur Ergänzungen dazu |
| [demodaten/](demodaten/) | Demobestände für Vorführung und Qualitätssicherung (Elektro Hofmeister, Ingenieurbüro …) |
| `config/` | Die Installation dieses Rechners, angesprochen ohne Namen (`./paper-werk up`). Ein eigener Ordner oder ein geklontes Config-Repo; dieses Repo ignoriert ihn. |
| [config-repos/](config-repos/) | Mehrere Installationen auf einem Rechner (Entwicklung): je ein privates Repo `paper-werk-config-<name>`, angesprochen mit Namen (`./paper-werk up dev`). Siehe [config-repos/README.md](config-repos/README.md). |
| [paper-werk](paper-werk) | Die Kommandozeile für alle Installationen auf diesem Rechner (`./paper-werk -h`, unter Windows `paper-werk.cmd`): anlegen, starten, prüfen, einrichten, aktualisieren. Sie setzt die Compose-Dateien zusammen, damit sie niemand kopieren muss. |
| [setup/](setup/) | Die Setup-Skripte selbst (projektunabhängig; per `--project <ordner>` auf den Ordner einer Installation angewendet, siehe [setup/README.md](setup/README.md)). Sie lesen die Werte aus `<projekt>/einstellungen/`. |
| [n8n/](n8n/) | Die n8n-Workflows (Quelle) |
| [docs/](docs/) | Hintergrund und Entscheidungen (Zugang, Wiederherstellung, Object Lock …) |
| [helpers/](helpers/) | Einzelne Runbooks und Notizen (z. B. Komplett-Reset aller Daten) |

## Installationen

Die Konfiguration einer Installation liegt nicht in diesem Repo. Ein Rechner
mit einer Installation hat sie in `config/`, ein Entwicklungsrechner mit
mehreren unter `config-repos/paper-werk-config-<name>`. Ein Kunde sieht so nur
seine eigene Konfiguration. Einzelheiten in
[config-repos/README.md](config-repos/README.md).

## Wie eine Installation aufgebaut ist

Eine Installation startet die Compose-Dateien aus `compose/` und kopiert sie
nicht. Zu einer Installation gehören nur diese Dateien:

| Im Installationsordner | Was es ist |
| --- | --- |
| `instanz.conf` | Welche Compose-Dateien gelten: Projektname, HTTPS ja/nein, Profile, eigene Zusätze |
| `.env`, `.env.*` | Die Werte dieser Installation: Pfade, Passwörter, Namen. Nicht versioniert. |
| `einstellungen/` | Was die Setup-Skripte einspielen: Paperless-Starterpaket, n8n-Liste, Kopia-Ignores |
| `compose.override.yml` | *Optional:* eigene Änderungen an der Zusammenstellung vor Ort. Wird automatisch dazugenommen. |

Gestartet wird aus der Repo-Wurzel:

```bash
./paper-werk                               # Installationen und was läuft
./paper-werk up kunde                        # docker compose up -d
./paper-werk up kunde --build
./paper-werk stop kunde                      # anhalten, Container bleiben
./paper-werk down kunde                      # Container entfernen, Daten bleiben
./paper-werk compose kunde logs -f paperless # jeder andere docker-compose-Befehl
./paper-werk compose kunde config            # die zusammengesetzte YAML
./paper-werk command kunde                   # nur den docker-compose-Aufruf zeigen
./paper-werk switch kunde                    # alle anderen anhalten, diese starten
```

Ohne Namen gilt `config/`. Unter Windows `paper-werk.cmd`, Hilfe mit `-h`.

### Betrieb

```bash
./paper-werk doctor kunde            # Zustandsbericht
./paper-werk update kunde            # prüfen, sichern, pull, bauen, starten, nachsehen
./paper-werk update kunde --trocken  # nur zeigen, was geschähe
```

`doctor` ist der Bericht, den ein Systembetreuer bei Problemen schickt. Er
meldet unter anderem lokale Änderungen in `compose/`, `config-template/`,
`setup/` oder `n8n/`; `update` bricht in diesem Fall ab, damit kein
Git-Konflikt mitten im Update entsteht.

Die Compose-Dateien werden nicht in die Installation kopiert, weil eine Kopie
bei Updates nicht nachgezogen wird und Abweichungen davon unbemerkt bleiben.
Änderungen für eine einzelne Installation gehören in eine
`compose.override.yml` im Installationsordner. Änderungen in `compose/`
führen beim nächsten `git pull` zu einem Konflikt.

## Auf Paperless-ngx v3 aktualisieren (Breaking Changes)

Für den Wechsel auf Paperless-ngx v3 reichen `pull` und `up -d` nicht. Zwei
Umgebungsvariablen sind ab v3 Pflicht; ohne sie startet der Container nicht
oder verhält sich anders:

1. **Voraussetzung:** Die laufende Instanz muss auf v2.20.15 sein, bevor auf v3 gesprungen wird
   (ältere Versionen erst dorthin aktualisieren). Version prüfen:

   ```bash
   docker inspect <paperless-container> --format='{{index .Config.Labels "org.opencontainers.image.version"}}'
   ```

2. **In der `.env.paperless` des jeweiligen Projekts ergänzen**, bevor gepullt wird:

   ```bash
   PAPERLESS_SECRET_KEY=<langer zufälliger String>   # ab v3 Pflicht, vorher optional
   PAPERLESS_DBENGINE=postgresql                       # ab v3 Pflicht bei Postgres/MariaDB,
                                                        # vorher aus PAPERLESS_DBHOST abgeleitet
   ```

   Secret Key generieren: `openssl rand -base64 48` (in Git Bash, auf Mac und Linux
   überall vorhanden). Git Bash bringt kein `python3` mit, deshalb `openssl`.
3. **Verhaltensänderung beachten:** Duplikate werden ab v3 standardmäßig nicht mehr abgelehnt.
   Altes Verhalten beibehalten: `PAPERLESS_CONSUMER_DELETE_DUPLICATES=true` setzen.
4. **Sicherung vor dem Upgrade**: Kopia-Snapshot ziehen, siehe
   [docs/kopia-backblaze.md](docs/kopia-backblaze.md).
5. Danach normal aktualisieren:

   ```bash
   docker compose pull
   docker compose up -d
   ```

   Die DB-Migration (inkl. Neuberechnung aller Dokument-Checksummen und Suchindex-Wechsel auf
   Tantivy) läuft automatisch beim Start des `paperless`-Containers. Logs prüfen
   mit `docker compose logs -f paperless`.

Details: [Migration-Guide der Paperless-ngx-Doku](https://docs.paperless-ngx.com/migration-v3/).

## Lizenz

Paper-Werk ist freie Software und steht unter der
[GNU Affero General Public License v3 (AGPL-3.0)](LICENSE).
Copyright (C) 2026 Horst Amper / KI-Werkstatt.

Für Beiträge gelten die Bedingungen aus
[CONTRIBUTING.md](https://github.com/paper-werk/paper-werk-app/blob/main/CONTRIBUTING.md)
der Anwendung.
