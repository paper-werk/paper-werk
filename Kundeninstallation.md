# Kundeninstallation

Anleitung für eine **komplett neue Installation auf einem Kundenrechner**
(Windows, Mac oder Linux), gedacht für jemanden, der das zum ersten
Mal macht. Ergebnis: laufender Paperless-ngx + n8n + Kopia-Backup-Stack,
befüllt mit dem Starterpaket (Tags, Dokumenttypen, Custom Fields,
Arbeitsabläufe, n8n-Workflows, Backup-Policy).

---

> **Beim Kunden vorher abfragen,** was er stellen muss: Rechner, DNS-Name,
> Zertifikat, Entra-Registrierung, Sicherungsziel (Abschnitt 7 und 8).

---

## 1. Voraussetzungen installieren

### Docker

- **Windows/Mac:** Docker Desktop installieren (docker.com/products/docker-desktop).
- **Linux:** Docker Engine + Compose Plugin (Distributions-Paketquelle oder
  offizielles Install-Skript von docker.com).

### Eine Bash-Shell (zum Ausführen der `.sh`-Setup-Skripte)

- **Mac/Linux:** schon vorhanden, das normale Terminal benutzen,
  nichts zu installieren.
- **Windows:** Windows bringt kein Bash mit, die Skripte sind aber
  `.sh`-Dateien. **Ja, das wird wirklich gebraucht.** Empfohlen: **[Git für
  Windows](https://git-scm.com/download/win)** installieren. Das bringt
  „Git Bash" **und** die `git`-Kommandozeile in einem mit, man braucht also
  ohnehin nur diese eine Installation (Repo holen *und* Skripte ausführen).
  Alternative für alle, die schon WSL eingerichtet haben: geht auch, ist aber
  aufwendiger einzurichten, wenn es das noch nicht gibt.

> **Wer beides hat, muss aufpassen, welches `bash` startet.** Auf einem
> Rechner mit WSL *und* Git Bash gewinnt im PATH meist WSL, und dann greift
> die jq-Falle unten. Im Zweifel Git Bash ausdrücklich aufrufen:
> `"C:\Program Files\Git\bin\bash.exe" ./setup/...`
> Typisches Fehlerbild: Die Setup-Skripte laufen in WSL statt in Git Bash, und
> der Fehler zeigt auf jq statt auf die Shell.

### jq (JSON-Werkzeug, für die Setup-Skripte)

- **Windows** (in Git Bash oder PowerShell): `winget install jqlang.jq`
  - danach ein **neues** Terminalfenster öffnen (PATH wird erst dann aktiv).
  - **Nur für Git Bash.** Wer die Skripte in WSL ausführt, braucht jq *dort*:
    `sudo apt install jq`. Das per winget installierte `jq.exe` ist ein
    Windows-Programm. Es taucht in WSL unter anderem Namen auf und versteht
    dessen Pfade (`/mnt/c/...`) nicht. Ein Symlink hilft deshalb nicht: Der
    Aufruf gelingt, und jq meldet dann `Could not open file` für jede Datei.
- **Mac:** `brew install jq`
- **Linux:** `sudo apt install jq` (Debian/Ubuntu) bzw. `sudo dnf install jq`
  (Fedora)

### Python 3.8 oder neuer (für `./paper-werk`)

- **Linux:** meist vorhanden (`python3 --version`), sonst `sudo apt install python3`.
- **Mac:** `brew install python`.
- **Windows:** `winget install Python.Python.3.13`, danach ein neues Terminal.

Ohne Python geht alles außer `./paper-werk` auch über die Shell-Skripte;
Schritt 4 nennt den Weg.

### curl

Auf Mac/Linux praktisch immer vorinstalliert. Auf Windows in Git Bash und in
aktuellem PowerShell ebenfalls schon dabei.

---

## 2. Vorbereitungs-Check

Bevor es losgeht, im Terminal (Windows: **Git Bash**, nicht PowerShell/cmd)
kurz prüfen, ob alles bereit ist:

```bash
docker info --format '{{.ServerVersion}}'   # Docker läuft?
jq --version                                 # jq installiert?
curl --version                               # curl installiert?
python3 --version || python --version        # Python ab 3.8?
```

Alle vier sollten eine Versionsnummer ausgeben. Kommt stattdessen
`command not found` oder ähnliches, fehlt das jeweilige Programm noch -
siehe Schritt 1.

---

## 3. Repo besorgen

```bash
git clone https://github.com/paper-werk/paper-werk.git
cd paper-werk
```

Mehr wird nicht gebraucht. Die Anwendung paper-werk-app kommt als fertiges
Image aus der Registry (`ghcr.io/paper-werk/paper-werk-app`), in der Version, die
`compose/docker-compose.yml` vorgibt. Solange das Paket privat ist, braucht
der Rechner einmal eine Anmeldung mit einem Token, das `read:packages` hat:

```bash
echo <token> | docker login ghcr.io -u <github-name> --password-stdin
```

**Updates ziehen** danach mit `./paper-werk update` (siehe
`README.md`, Abschnitt „Betrieb“) oder von Hand mit `git pull`.

**Selbst bauen statt laden** (etwa für eine eingehängte eigene App): Repo
`paper-werk-app` neben dieses klonen und in `config/instanz.conf`
`APP_BAUEN=ja` setzen. `./paper-werk` nimmt dann `compose/compose.build.yml`
dazu und baut aus dem Quelltext; `up --build` statt `up`.

---

## 4. Installation anlegen und starten

Die Konfiguration einer Installation liegt in `config/` in diesem Repo (von
Git ignoriert). Angelegt wird sie aus der Vorlage `config-template/`:

```bash
./paper-werk init                      # oder: ./paper-werk init --variante elektro
```

`init` kopiert die Vorlage nach `config/`, legt die `.env`-Dateien an, erzeugt
alle Kennwörter und Schlüssel, setzt die Containernamen in
`einstellungen/setup.conf` und stellt das Paperless-Starterpaket zusammen
(Basis plus Gewerksvariante, falls angegeben). Am Ende nennt es, was noch
auszufüllen ist. `init` überschreibt nie: Gibt es `config/` schon, bricht es
ab.

Ohne Python geht dasselbe von Hand:

```bash
cp -r config-template config
cd config
for v in .env*.example; do mv "$v" "${v%.example}"; done
cp einstellungen/setup.conf.example einstellungen/setup.conf
cd ..
./setup/paperless/starterpaket-zusammenstellen.sh config     # [variante]
```

Dann aber alle `change-me` selbst ersetzen und in `setup.conf` `kunde-xyz`
durch den Projektnamen aus `instanz.conf` (Vorgabe `paper-werk`).

### Was hier wem gehört

| Wo | Gehört | Beim Update |
| --- | --- | --- |
| `config/instanz.conf` | dem Betreiber | bleibt |
| `config/.env`, `config/.env.*` | dem Betreiber (**nicht im Git**) | bleibt |
| `config/einstellungen/**` | dem Betreiber | bleibt |
| `config/compose.override.yml` | dem Betreiber, *optional* | bleibt |
| `compose/**`, `config-template/**`, `setup/**` | uns | wird mit `git pull` nachgezogen |

**Wer an der Zusammenstellung des Stacks etwas ändern muss** (ein anderer
Port, ein zusätzliches Volume, ein Dienst weniger), legt dafür eine
`config/compose.override.yml` an. `./paper-werk` nimmt sie von allein dazu, und
ein `git pull` rührt sie nicht an.

**Nicht in `compose/` oder `config-template/` ändern.** Dort gewinnt beim
nächsten Update entweder Git mit einem Konflikt, oder die Änderung
verschwindet still.

`config/` kann ein eigenes Git-Repo werden, etwa um die Konfiguration
mehrerer Kunden getrennt zu verwahren (`.gitignore` liegt bei); dann holt
`./paper-werk update` es mit. Siehe `config-repos/README.md`.

### Was noch auszufüllen ist

`init` listet die Schlüssel, in denen noch `change-me` steht:

- **`.env.app`: `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS`.**
  In `ALLOWED_HOSTS` muss der Servicename `paper-werk-app` stehen bleiben;
  darüber erreichen n8n und Paperless die Anwendung. Fehlt er, meldet sich
  das erst beim ersten Automatisierungslauf, als `DisallowedHost`.
- **`.env.paperless`: `PAPERLESS_AI_LLM_API_KEY`** für die KI-Funktionen;
  ohne Schlüssel `PAPERLESS_AI_ENABLED=false` setzen.

> **In `ALLOWED_HOSTS` gehört jede Adresse, unter der ein MENSCH die
> Anwendung aufruft.** `localhost` allein genügt nur dem, der am Server
> selbst sitzt. Vom Arbeitsplatz aus braucht es die IP oder den
> Rechnernamen, sonst antwortet Django mit **400**. Dasselbe gilt für
> `DJANGO_CSRF_TRUSTED_ORIGINS`, nur mit Schema und Port; ohne das lädt die
> Anmeldeseite, das Absenden scheitert aber mit einem CSRF-Fehler.
>
> ```
> DJANGO_ALLOWED_HOSTS=paper-werk-app,localhost,127.0.0.1,192.168.1.50,SERVERNAME
> DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://192.168.1.50:8000
> ```
>
> **Für Paperless dasselbe** in `.env.paperless` unter
> `PAPERLESS_CSRF_TRUSTED_ORIGINS`, nur mit Port 8005. Fehlt der Eintrag,
> funktioniert alles über `localhost`, über die IP kommt 400.

**`KOPIA_PASSWORD` in `.env.kopia` zusätzlich in den Passwortmanager.**
`init` hat es erzeugt; ohne es sind spätere Backups nicht mehr lesbar.

In `.env.app` steht auch der **Block zur Archivanbindung** (`PAPERLESS_URL`,
`PAPERLESS_ANSICHT_URL`, `PAPERLESS_ARCHIVIERUNG`). Die Vorgaben passen für
den Stack; `PAPERLESS_TOKEN` bleibt vorerst leer und wird in Schritt 5
nachgetragen. **Ohne diesen Block wandert kein festgeschriebener Beleg ins
Archiv**, und zwar geräuschlos.

### Wo die Daten liegen

In benannten Docker-Volumes (`<projekt>_pgdata`, `<projekt>_media` …), die
Docker selbst anlegt und verwaltet: unter Linux in `/var/lib/docker/volumes`,
unter Docker Desktop in dessen VM. Als Ordner auf dem Host sind sie bewusst
nicht sichtbar; wer an Datenbank oder Ablage vorbei Dateien verschiebt,
beschädigt Paperless.

**`docker compose down -v` löscht alle Daten.** `./paper-werk down` entfernt nur die
Container.

Kopia sichert alle Volumes über eine Quelle `/source/paper-werk`, dazu
`config/` mit `.env` und Zertifikat. Die Sicherung ist damit vollständig:
Ein Restore bringt auch die Kennwörter zurück, mit denen die Datenbanken
angelegt wurden.

**Scanner-Ablage per SMB (optional).** Soll ein Scanner oder Kopierer
direkt in Paperless ablegen, wird `consume` ein Ordner auf dem Host, den
der Admin per SMB freigibt. In `config/.env`:

```bash
PAPER_WERK_CONSUME_ORDNER=/srv/scans          # Windows: C:/Scans
```

`./paper-werk` hängt dann den Ordner statt des Volumes ein. Unter Docker
Desktop (Windows, Mac) zusätzlich in `.env.paperless`
`PAPERLESS_CONSUMER_POLLING_INTERVAL=10`: Dateiereignisse vom Host kommen in
der VM nicht an, ohne Polling sähe Paperless die Scans nie. Unter Linux
nicht nötig. Nur `consume` freigeben, nie Daten- oder Datenbankordner.

**Export** (`document_exporter`) ist im Standard nicht als Ordner
eingehängt. Wer ihn braucht, legt ihn in `config/compose.override.yml` an
(`- /srv/export:/usr/src/paperless/export`), auf demselben Weg wie consume.

### Starten

Stack starten, aus der Repo-Wurzel. Ohne Namen gilt `config/`:

```bash
./paper-werk compose pull
./paper-werk up                # docker compose up -d
```

Welcher `docker compose`-Befehl aus `instanz.conf` wird, zeigt
`./paper-werk command`.

Prüfen:

```bash
./paper-werk compose ps
curl http://localhost/                    # Einstiegsseite
curl http://localhost:8000/api/v1/status/ # paper-werk-app (Lebenszeichen)
curl http://localhost:8005                # Paperless
curl http://localhost:5678                # n8n
```

Paperless kann beim allerersten Start 1 bis 2 Minuten für die
Datenbank-Migrationen brauchen, bevor `curl` antwortet; `paper-werk-app`
migriert beim Start ebenfalls selbst.

**Die Einstiegsseite unter `http://localhost/`** ist der gemeinsame Eingang,
eine kleine Seite mit Verweisen auf die Komponenten
(`compose/caddy/html/index.html`). Die Verweise tragen automatisch den
Namen, unter dem die Seite aufgerufen wurde, und das richtige Schema.

Wer eine **eigene** Seite will, kopiert den Ordner:

```bash
cp -r compose/caddy config/caddy
```

`./paper-werk` nimmt dann diesen statt des Ordners der Vorlage. Das ist die
einzige Kopie, die vorgesehen ist, und sie betrifft nur die Seite.

---

## 5. Starterpaket einspielen

Jetzt kommen die Setup-Skripte aus `setup/` ins Spiel. Sie füllen die
frische Installation mit Tags, Dokumenttypen, Custom Fields,
Arbeitsabläufen, n8n-Workflows und der Kopia-Backup-Policy. Ausführliche
Doku: [setup/README.md](setup/README.md).

Die Werte dazu liegen in `config/einstellungen/`; `init` hat sie aus
`config-template/einstellungen/` angelegt:

| Datei | Stand nach `init` |
| --- | --- |
| `setup.conf` | Containernamen und Admin-Kennwort der App gesetzt; Token fehlt noch (unten) |
| `n8n/config.json` | Adressen der Instanz; **vor dem n8n-Modul prüfen** |
| `n8n/workflows.list` | welche Workflows importiert werden |
| `n8n/credentials.json` | optional, aus `credentials.json.example` |
| `kopia/ignore.rules` | was Kopia auslässt |
| `paperless/starterpaket/*.json` | zusammengestellt aus `starterpakete/basis/` (+ Variante) |

**`config.json` vor dem n8n-Modul ausfüllen.** Fehlt sie, importiert das
Modul zwar alle Workflows, legt aber die Data Table `pw_config` nicht an,
und ohne die bricht jeder Workflow im Konfigurations-Node ab.

**Gewerksvarianten** (`./paper-werk init --variante elektro`) ergänzen das
Basispaket, beim Elektrobetrieb etwa um die Dokumenttypen *Prüfprotokoll*,
*Netzanmeldung* und *Abnahmeprotokoll*, die Tags *Gewährleistung*,
*Prüfung fällig* und *Förderung* sowie die Ansicht *Prüfungen fällig*. Eine
Variante enthält nur ihre Ergänzungen; doppelte Namen weist die
Zusammenstellung ab. Nachträglich: `FORCE=1
./setup/paperless/starterpaket-zusammenstellen.sh config elektro`.

`einstellungen/setup.conf` und `einstellungen/n8n/credentials.json`
enthalten Secrets und sind gitignored, auch wenn `config/` ein Git-Repo
wird. `einstellungen/n8n/config.json` ist versioniert: Adressen und URLs,
keine Geheimnisse.

**Paperless-API-Token erzeugen** (Adminname anpassen, falls abweichend von
`admin`):

```bash
./paper-werk compose exec paperless python3 manage.py drf_create_token admin
```

Gibt eine Zeile `Generated token <...>` zurück. Der Token wird gleich
**an zwei Stellen** gebraucht.

> **Der Token muss auch in `.env.app`**, und danach muss der App-Container neu
> starten. Das wird leicht übersehen, weil `.env.app` in Schritt 4 schon
> einmal ausgefüllt wurde; damals gab es den Token aber noch nicht, denn er
> entsteht erst aus dem laufenden Paperless. Ohne diesen Schritt bricht
> `manage.py paperless_einrichten` ab mit *"Paperless ist nicht eingerichtet"*,
> und die Meldung zeigt auf die Einstellung statt auf den vergessenen
> Neustart.
>
> ```bash
> # PAPERLESS_TOKEN in .env.app eintragen, dann aus der Repo-Wurzel:
> ./paper-werk up paper-werk-app
> ```
>
> Der Container liest seine `.env`-Dateien nur beim Start; eine geänderte
> Datei erreicht ihn nicht von selbst.

`einstellungen/setup.conf` öffnen und ausfüllen:

- `PAPERLESS_TOKEN`: der Token von eben
- `PAPERLESS_CONTAINER` / `N8N_CONTAINER` / `KOPIA_CONTAINER` / `APP_CONTAINER`: Containernamen prüfen
  mit `./paper-werk compose ps --format '{{.Name}}'`
  Über `PAPERLESS_CONTAINER` spricht das Setup
  Paperless und die App **im Container** an statt über die Ports des Hosts.
  Nur so geht es auch mit HTTPS (`compose.https.yml`), wo beide keinen
  eigenen Port mehr haben. Fehlt der Wert, warnt das Setup und nimmt den
  alten Weg über `PAPERLESS_URL`, der nur ohne HTTPS funktioniert.
- `APP_ADMIN_USER` / `APP_ADMIN_PASSWORD`: der erste Benutzer der Anwendung.
  **Ohne ihn kommt niemand hinein**: Django legt von sich aus keinen an. Die
  Werte werden nur beim Anlegen benutzt; ein späterer Setup-Lauf lässt einen
  vorhandenen Benutzer unangetastet und setzt sein Passwort nicht zurück.
- `APP_DIENSTZUGANG`: Name des Dienstkontos für n8n (ausgeliefert: `n8n`).
  Das Setup gibt dessen Schlüssel aus; er ist das Gegenstück zum
  `PAPERLESS_TOKEN` und gehört in die n8n-Credential für die Anwendung. Leer
  lassen überspringt den Schritt.
- `KOPIA_REPO_TYPE`: `disk` (lokal/externe Platte) oder `s3` (Cloud, dann
  zusätzlich `S3_BUCKET`/`S3_ENDPOINT`/`S3_ACCESS_KEY`/`S3_SECRET_KEY`
  ausfüllen). **Auch für Backblaze B2 `s3` verwenden**, nicht `b2`: Kopias
  eigener b2-Provider ist deprecated, dasselbe Bucket ist über den
  S3-kompatiblen Endpunkt erreichbar.
  Bei Backblaze zusätzlich **drei Dinge erledigen**, die man leicht übersieht
  und die später teuer bzw. gefährlich werden. Ablauf, Kosten und Verifikation
  stehen vollständig in [docs/object-lock.md](docs/object-lock.md), der
  Hintergrund zum Backup selbst in
  [docs/kopia-backblaze.md](docs/kopia-backblaze.md):
  1. **Object Lock beim Anlegen des Buckets aktivieren.** Nachträglich geht es
     nicht; wer es vergisst, muss das Bucket neu anlegen. Danach im Repository
     einschalten:
     `kopia repository set-parameters --retention-mode=GOVERNANCE --retention-period=7d`
  2. Bucket → Lifecycle Settings → *"Keep only the last version of the file"*.
     Sonst behält Backblaze jeden von Kopia gelöschten Blob als versteckte
     Version und berechnet ihn weiter (siehe `docs/kopia-backblaze.md`).
  3. Application Key auf genau dieses eine Bucket beschränken, Capabilities nur
     `listBuckets`, `listFiles`, `readFiles`, `writeFiles`, `deleteFiles`,
     `readFileRetentions`, `writeFileRetentions`, also **sieben**, und den Key
     **per API anlegen**. Die Schaltfläche *"Read and Write"* im Web-UI vergibt
     25 Capabilities inklusive `bypassGovernance`, und die hebelt Object Lock
     aus: ein Key damit darf trotz Sperre löschen.

n8n-Credentials optional in `einstellungen/n8n/credentials.json` ausfüllen (die Datei
wurde oben mitkopiert; ohne sie wird der Credential-Import übersprungen) -
siehe [setup/README.md](setup/README.md#wie-die-inhalte-gepflegt-werden).

**Achtung: derselbe Paperless-Token gehört an zwei Stellen**, in
`einstellungen/setup.conf` (für die Setup-Skripte) *und* in die Credential
„Header Auth paperless" in `einstellungen/n8n/credentials.json` (für die Workflows).
Wer eine `credentials.json` von einer anderen Installation übernimmt, schleppt
deren Token mit, und der passt nicht zur frischen Datenbank. Der Fehler ist
still: Paperless feuert den Webhook und entfernt den Kommando-Tag, n8n
scheitert mit `Authorization failed`, und am Dokument sieht man nur, dass
nichts passiert ist. `apply.sh` warnt, wenn die beiden Werte
auseinanderlaufen.

**`einstellungen/n8n/config.json` ausfüllen**. Hier stehen die Adressen und URLs
dieser Installation, und zwar für alle Workflows gemeinsam. Das Setup schreibt
sie in die n8n-Data-Table `pw_config`; die Workflows lesen sie zur Laufzeit von
dort. In den Workflows selbst steht keine Adresse mehr.

Pflicht sind vier Zeilen:

| `key` | was hineingehört |
| --- | --- |
| `mail_betrieb` | Empfänger aller Berichte, Erinnerungen und Störungsmeldungen |
| `mail_absender` | Absender aller Mails; **muss zur SMTP-Credential passen**, der Mailserver bindet den Absender an die authentifizierte Mailbox |
| `instanz` | Name dieser Anlage, steht im Betreff der Störungsmeldungen (z. B. `mueller-gmbh`) |
| `paperless_url_oeffentlich` | die Adresse, unter der der Empfänger Paperless im Browser erreicht; sie landet in den Links der Mails |

`paperless_url` (`http://paperless:8000`) bleibt in aller Regel wie vorgegeben:
das ist der Docker-interne Servicename für die API-Aufrufe, nicht die
Browser-Adresse. Die übrigen Zeilen (`mail_duo`, `mail_stb`,
`mail_sevdesk_absender`) sind nur nötig, wenn der zugehörige Export-Workflow
verwendet wird. Sie dürfen leer bleiben und lassen sich jederzeit nachtragen.

Nachträglich ändern geht ohne Skript und ohne Neustart: n8n-Oberfläche →
**Data Tables** → `pw_config`. Die Spalte `hint` steht dort neben jedem
Wert und erklärt, was gemeint ist.

**Setup ausführen** (aus `setup/`, mit `--project` auf den
Projektordner zeigend). **Windows: zwingend in Git Bash**, nicht in
PowerShell oder cmd, siehe Troubleshooting unten:

```bash
cd ../../setup
bash setup.sh --project ../config
```

`bash setup.sh` statt `./setup.sh` ist Absicht: So läuft das Skript auch dann,
wenn beim Klonen das Unix-Ausführungsrecht verlorengegangen ist; ein `chmod`
ist dann nicht nötig.

Spielt alle vier Module ein (paper-werk-app, Paperless-Starterpaket,
n8n-Workflows, Kopia-Backup). Kann gefahrlos mehrfach laufen (idempotent) -
legt nichts doppelt an und setzt insbesondere kein Passwort zurück.

---

## 6. Verifizieren

- **Einstiegsseite** (`http://localhost/`): zeigt die Kacheln und darunter den
  Abschnitt für Betrieb und Support. Ein Klick auf jede Kachel muss dort
  landen, wo sie hinzeigt. Das prüft zugleich, ob die Adresse stimmt, unter
  der die Installation im Netz erreichbar ist.
- **paper-werk-app** (`http://localhost:8000/admin/`, Login mit
  `APP_ADMIN_USER`/`_PASSWORD` aus `setup.conf`): Anmeldung möglich, und unter
  *Benutzer → Gruppen* stehen fünf: `paper-werk-buero`,
  `paper-werk-projektleitung`, `paper-werk-superuser`, „Faktura Dienst" und
  „Belegübernahme". Fehlen sie, kann ein Bürokonto nichts tun und der
  Dienstzugang bekommt auf jede Anfrage 403. Der Dienstzugang (`n8n`) steht
  in den beiden letzten. Ohne „Belegübernahme“ holt n8n zwar Belege ab,
  aber keine Eingangsrechnung aus dem Archiv herüber. Prüfen lässt sich das
  auch von außen:
  ```bash
  docker exec paper-werk-paper-werk-app-1 uv run --no-dev python manage.py shell -c     "from django.contrib.auth.models import Group; print(', '.join(g.name for g in Group.objects.order_by('name')))"
  ```
- **Textbausteine** (in der Anwendung unter *Stammdaten → Textbausteine*):
  17 Stück, von „Anrede" bis zu den Mail-Anschreiben je Belegart. Die
  Grußformel hat noch keine Namenszeile, solange keine eigene Firma angelegt
  ist. Nach dem Anlegen der Firma den Baustein „Grußformel" löschen und
  `./paper-werk compose exec paper-werk-app uv run --no-dev python manage.py faktura_textbausteine`
  erneut laufen lassen. Eine Anlage ohne Bausteine bekommt sie mit
  `bash setup.sh --project … app` nachgeliefert.
- **Der Beleg-Ablageordner** ist das Volume `app-media`. Dort landen die festgeschriebenen
  Rechnungen, also aufbewahrungspflichtige Daten. Prüfen lässt sich das später
  jederzeit mit
  `./paper-werk compose exec paper-werk-app uv run --no-dev python manage.py pruefe_belegarchiv`:
  Der Befehl hält jeden festgeschriebenen Beleg gegen seine Datei und deren
  Prüfsumme und endet bei Beanstandung mit Exit-Code 1, gedacht für einen
  Cron-Lauf nach der Datensicherung.
- **Paperless** (`http://localhost:8005`, Login wie in `.env` eingetragen):
  unter Einstellungen prüfen, ob Tags/Dokumenttypen/Korrespondenten/
  Arbeitsabläufe da sind; die gespeicherten Ansichten stehen links in der
  Seitenleiste. Die Tags „Paper-Werk senden" und „Paper-Werk gesendet" legt
  nicht das Starterpaket an, sondern das Modul app (`paperless_einrichten`) -
  fehlen sie, lief es vor dem Paperless-Token in `.env.app`. Dessen Ausgabe
  beim ersten Lauf ist irreführend: Vor jedem „angelegt“ steht „… gibt es
  dort nicht; das Feld bleibt leer.“ Das ist nur der Blick ins Archiv vor
  dem Anlegen, kein Fehler. Maßgeblich ist „9 Einträge angelegt.“
- **n8n** (`http://localhost:5678`): importierte Workflows sind sichtbar. Aktiv
  sind nur die vier Webhook-Workflows ohne Mailversand. Alles, was Mail
  verschickt, bleibt bewusst deaktiviert, bis Empfängeradressen und
  SMTP-Zugang gesetzt sind (Begründung in `einstellungen/n8n/workflows.list` im
  Projektordner). Vor dem Aktivieren die jeweiligen Credentials
  (Mistral/sevDesk/…) eintragen.
- **Instanz-Einstellungen** (n8n → **Data Tables** → `pw_config`): die Tabelle
  ist da und die vier Pflichtzeilen haben Werte. `apply.sh` warnt am Ende
  namentlich, welche Zeilen noch leer sind. Ein
  Workflow, dem sein Wert fehlt, bricht ab, statt Falsches zu verschicken.
- **Fehlermeldung testen**: `fehler-melden-test` einmal aktivieren, den Webhook
  aufrufen, Postfach kontrollieren, wieder deaktivieren. Dieser Test ist nicht
  optional; scheitert `fehler-melden` selbst (falsche SMTP-Credential, leere
  `pw_config`), verschluckt n8n das kommentarlos.
- **Kopia** (`http://localhost:51515`, Login mit `KOPIA_SERVER_USERNAME`/
  `_PASSWORD` aus `.env`): Repository und erster Snapshot sollten sichtbar
  sein. **Im Snapshot nachsehen, ob `app-pgdata` und `app-media` enthalten
  sind**, denn das sind die Rechnungsdaten. Ein Backup, das sie nicht enthält, ist
  bei aufbewahrungspflichtigen Daten keines. Sie liegen unter derselben Wurzel
  wie alles andere und sind deshalb automatisch dabei; nachsehen kostet
  trotzdem nur einen Blick.

---

## 6a. Optional: eigener Name und eigenes Logo

Ein Betrieb, dem „Paper-Werk" nicht gefällt, nennt die Anwendung, wie er
will. Drei Zeilen in `.env.app`, eine Bilddatei im Medienordner:

```bash
# 1. Logo ablegen - im Volume app-media, nicht im Quellordner der App
./paper-werk compose exec paper-werk-app mkdir -p /app/media/marke
./paper-werk compose cp logo.svg paper-werk-app:/app/media/marke/

# 2. In .env.app des Projektordners eintragen
PAPER_WERK_MARKE_NAME=Belegwerk
PAPER_WERK_MARKE_UNTERTITEL=Verwaltung und Abrechnung
PAPER_WERK_MARKE_LOGO=marke/logo.svg

# 3. Der Container liest seine .env nur beim Start
./paper-werk compose restart paper-werk-app
```

Alle Werte mit Begründung stehen in `config-template/.env.app.example`, Abschnitt
*Name und Logo der Anwendung*.

**Was mitzieht und was nicht.** Es zieht mit, was der Anwender bei der
täglichen Arbeit sieht: Browsertab, Kopf der Seitenleiste, Anmeldeseite und
die Seiten rund um die Anmeldung über Microsoft. Es bleibt, was nur sieht,
wer die Anlage betreut: Variablennamen, Containernamen, Protokollzeilen,
die Schnittstelle. Und es bleiben die Gruppen `paper-werk-buero`,
`-projektleitung` und `-superuser`: Sie heißen in Entra ID, in Paperless und
in der App gleich (Abschnitt 7.5). Die Belege sind nicht betroffen, sie
tragen von jeher die Firma des Kunden.

**Prüfen, ob die Datei ankommt.** Fehlt das eingestellte Logo im Volume,
zeigt die Oberfläche wieder ihr Symbol, ohne Fehlermeldung. Sichtbar wird
das nur so:

```bash
./paper-werk compose exec paper-werk-app uv run --no-dev python manage.py check
# meldet paperwerk.W002, wenn ein eingestelltes Bild nicht im Medienordner liegt
```

**Das Archiv zieht nicht mit.** Paperless trägt seinen eigenen Namen und
bringt dafür eigene Einstellungen mit (`PAPERLESS_APP_TITLE` und
`PAPERLESS_APP_LOGO` in `.env.paperless`), in diesem Stack noch nicht
erprobt, also vor dem Zusagen an der eingesetzten Fassung nachsehen. Wer die
App umbenennt, sollte das Archiv daneben jedenfalls nicht vergessen: Die
beiden stehen auf derselben Einstiegsseite.

---

## 7. Optional: HTTPS und Anmeldung über Microsoft

Zwei Ausbaustufen, die zusammengehören, aber getrennt eingerichtet werden.
**Anmeldung über Microsoft setzt HTTPS voraus**, sobald der Server nicht
`localhost` heißt: Microsoft nimmt Rückleitadressen mit `http://` nur für
`localhost` an. Die Abwägung steht in `docs/zugang-und-authentifizierung.md`.

### 7.1 Was vorher geklärt sein muss

| Was | Wer liefert es |
| --- | --- |
| Ein **Name** für den Server im Netz des Kunden, z. B. `paper-werk.kunde.de`, mit DNS-Eintrag auf die IP des Servers. Ohne DNS-Server: siehe [docs/lokaler-name.md](docs/lokaler-name.md) | IT des Kunden |
| **Woher das Zertifikat kommt**, siehe 7.2 | Entscheidung mit der IT des Kunden |
| Die Ports **80, 443, 8000, 8005** auf dem Server frei | IT des Kunden |
| Für Microsoft: ein Konto mit Administratorrechten im **Entra-Portal** des Kunden, und dessen **Tarif** (siehe 7.5) | IT des Kunden |

### 7.2 Zwei Wege zum Zertifikat

`PAPER_WERK_TLS_MODE` in `.env` wählt:

- **`datei`**: Der Kunde stellt das Zertifikat aus, typisch aus der
  Zertifizierungsstelle seiner Windows-Domäne. Die Arbeitsplätze vertrauen
  ihm dann von selbst. Gebraucht werden zwei Dateien im PEM-Format:
  `zertifikat.pem` (**mit** Zwischenzertifikat, falls es eines gibt) und
  `schluessel.pem` (**ohne** Passphrase). Liefert die IT eine `.pfx`:

  ```bash
  openssl pkcs12 -in server.pfx -nokeys  -out zertifikat.pem
  openssl pkcs12 -in server.pfx -nocerts -nodes -out schluessel.pem
  ```

  Beide Dateien in einen Ordner **außerhalb** des Repos, oder in
  `config/zertifikate/`; nur dieser Name ist in `.gitignore`
  ausgeschlossen. Im Schlüssel steckt die Identität des Servers.

  **Das Zertifikat läuft ab**, typisch nach ein bis zwei Jahren, und dann
  öffnet kein Browser paper-werk mehr. Die Erneuerung ist Sache des Kunden -
  so in die Vereinbarung. 30 Tage vorher zeigt paper-werk der Verwaltung
  auf der Startseite einen Hinweis.

- **`intern`**: Caddy erzeugt eine eigene kleine Zertifizierungsstelle. Kein
  Zutun der IT, aber jeder Arbeitsplatz installiert **einmal** deren
  Stammzertifikat (7.4). Caddy erneuert selbst; das Stammzertifikat gilt zehn
  Jahre. Es liegt in `caddy-data` und damit in der Sicherung. Geht es
  verloren, muss jeder Arbeitsplatz neu installieren.

### 7.3 HTTPS einschalten

In `.env` ergänzen:

```bash
PAPER_WERK_HOSTNAME=paper-werk.kunde.de
PAPER_WERK_TLS_MODE=datei                      # oder intern
PAPER_WERK_CERT_PATH=/pfad/zum/ordner   # nur bei datei
```

`.env.app` und `.env.paperless` bleiben, wie sie sind: Alle Adressen, die App
und Paperless kennen müssen, leitet `compose.https.yml` aus dem Namen ab.

In `einstellungen/setup.conf` muss `PAPERLESS_CONTAINER` stehen. Ohne ihn kann das Setup Paperless im HTTPS-Betrieb nicht
erreichen; es warnt dann und bricht ab.

In `instanz.conf` `HTTPS=ja` setzen. Damit nimmt `./paper-werk` das
Zusatzstück `compose/compose.https.yml` dazu:

```bash
./paper-werk up
```

**Was gilt am Ende?** `compose.https.yml` enthält nur, was sich gegenüber der
Vorlage ändert. Das hält beide Dateien gleich, ist beim Lesen aber
undurchsichtig. Die fertige, zusammengelegte Fassung, so wie Docker sie
tatsächlich benutzt, gibt Compose selbst aus:

```bash
./paper-werk compose config
```

Das ist genauer als jede von Hand gepflegte Gesamtdatei, und die würde mit der
Zeit von der Vorlage abweichen. Nur die Unterschiede zu http:

```bash
# einmal mit HTTPS=nein in instanz.conf, einmal mit HTTPS=ja
./paper-werk compose config > ohne.yml
./paper-werk compose config > mit.yml
git diff --no-index ohne.yml mit.yml
```

**Vorsicht:** Die Ausgabe enthält alle Werte aus den `.env`-Dateien im
Klartext, auch Passwörter und Schlüssel. Nicht weitergeben, nicht einchecken,
danach löschen.

Danach sind erreichbar:

| | |
| --- | --- |
| Einstiegsseite | `https://paper-werk.kunde.de/` |
| Angebote und Rechnungen | `https://paper-werk.kunde.de:8000/admin/` |
| Archiv | `https://paper-werk.kunde.de:8005/` |

`http://…:8000` und `http://…:8005` gehen **nicht** mehr, damit keine
unverschlüsselte Verbindung offen bleibt. n8n (5678) und Kopia (51515) bleiben,
wie sie sind: Werkzeuge für die Betreuung, nur im Netz des Kunden.

### 7.4 Nur bei `intern`: das Stammzertifikat auf jeden Arbeitsplatz

1. `https://paper-werk.kunde.de/` öffnen, die Warnung dieses eine Mal
   bestätigen.
2. Unten auf der Seite „Stammzertifikat für diesen Rechner" herunterladen.
3. Doppelklick → *Zertifikat installieren* → **„Alle Zertifikate in folgendem
   Speicher speichern"** → *Vertrauenswürdige Stammzertifizierungsstellen*.
   Nicht „automatisch auswählen“, weil es dann oft bei den
   Zwischenzertifizierungsstellen landet und der Browser weiter warnt.
4. **Den Browser mit `chrome://restart` bzw. `edge://restart` neu starten.**
   Fenster schließen reicht nicht: Chrome läuft im Hintergrund weiter und
   liest die Zertifikate nur beim Start, auch wenn Windows der Verbindung
   schon vertraut. Hilft das nicht:
   `chrome://certificate-manager` → „Importierte Zertifikate aus Ihrem
   Betriebssystem verwenden" einschalten.
5. Firefox führt einen eigenen Speicher und will das Zertifikat dort noch
   einmal (Einstellungen → Datenschutz & Sicherheit → Zertifikate).

In einer Windows-Domäne kann die IT das Stammzertifikat stattdessen per
Gruppenrichtlinie verteilen; dann entfällt das für alle Arbeitsplätze.

### 7.5 Anmeldung über Microsoft

**Im Entra-Portal des Kunden** (`entra.microsoft.com`, das Portal ist oft
englisch):

1. *App registrations → New registration*: Name `paper-werk`, Kontotyp „nur
   dieses Organisationsverzeichnis". Auf der Seite *Overview* die
   **Application (client) ID** und die **Directory (tenant) ID** notieren.
2. *Authentication → Add a platform → Web*, zwei Rückleitadressen:
   `https://paper-werk.kunde.de:8000/accounts/oidc/entra/login/callback/` und
   `https://paper-werk.kunde.de:8005/accounts/oidc/entra/login/callback/`
   (der Schrägstrich am Ende gehört dazu).
3. *Certificates & secrets → New client secret*. Den Wert aus der Spalte
   **Value** sofort kopieren, er wird nur einmal angezeigt. Enthält er ein
   `$`, einen neuen erzeugen: Compose verstümmelt `$` in den `.env`-Dateien.
4. *Token configuration → Add optional claim → ID → email*. Sonst entstehen
   Konten ohne Mailadresse.
5. *App roles*: drei Rollen, Feld **Value** genau so:
   `paper-werk-buero`, `paper-werk-projektleitung`, `paper-werk-superuser`.
6. *Enterprise applications → paper-werk → Properties → Assignment required:
   Yes*. Wer keine Rolle hat, kommt dann gar nicht erst durch.
7. *Enterprise applications → paper-werk → Users and groups*: jeder Person
   **genau eine** Rolle geben.

**Tarif:** Im kostenlosen Entra-Tarif lassen sich Rollen nur einzelnen
Personen zuweisen, nicht Gruppen. Gruppen verlangen Entra ID P1, das in
Microsoft 365 Business Premium enthalten ist und in Business Standard nicht. Das ist
der Unterschied zwischen Pflege an einer Stelle und an jedem Konto einzeln.

**MFA** (zweiter Faktor) erzwingt der Kunde in seinem Tenant (Security
Defaults oder Conditional Access). paper-werk sieht davon nichts und muss es
nicht.

**Auf dem Server:** In `.env.paperless` und `.env.app` stehen die Blöcke
„Gemeinsame Anmeldung" auskommentiert. Einkommentieren und die Tenant-ID
(in der Discovery-Adresse), die Client-ID und das Geheimnis eintragen, in
beiden Dateien dieselben Werte. Danach neu starten und einmal:

```bash
cd setup
./setup.sh --project ../config sso
```

Das legt in Paperless die Gruppen an und gibt ihnen das Archiv frei (siehe
`setup/sso/apply.sh`). **Der erste Lauf auf einem großen Bestand hält den
Posteingang von Paperless einige Minuten auf** (574 Dokumente: knapp
sieben Minuten), also nicht während der Arbeitszeit. Weitere Läufe stoßen nur
an, was noch fehlt.

**Der lokale Login bleibt.** Das Passwortformular steht auch mit
Microsoft-Anmeldung auf der Anmeldeseite, und der lokale Verwalter aus
Schritt 5 kommt darüber herein, wenn Microsoft einmal nicht erreichbar ist.
Nicht löschen.

### 7.6 Prüfen

- Einstiegsseite über `https://…`, kein Warnhinweis im Browser.
- Anmeldung über Microsoft in der App **und** im Archiv, mit je einem Konto
  jeder Rolle.
- Ein Konto **ohne** Rolle wird abgewiesen (Microsoft meldet AADSTS50105).
- In der Rechnungsliste zeigt „Archiv" auf `https://…:8005/…`.
- Der lokale Verwalter kommt über das Passwortformular herein.

---

## 8. Vor dem ersten Rechnungsversand: E-Rechnung und Aufbewahrung

**Mit dem Kunden und seinem Steuerberater zu klären, nicht mit dem, der
später versendet.** In der Versandmaske steht dazu bewusst nichts: Wer dort
eine Rechnung verschickt, kann an der Aufbewahrung nichts ändern.

paper-werk erzeugt zu jeder Rechnung eine E-Rechnung (XML nach EN 16931,
für öffentliche Auftraggeber als XRechnung). Beim Versand lässt sich wählen:
PDF (die E-Rechnung steckt darin), XML oder beides.

> **GoBD: Nur das XML zu versenden ist nur zulässig, wenn das XML
> revisionssicher aufbewahrt wird.** Wer eine Rechnung ausschließlich als XML
> verschickt, macht das XML zum Original. Aufzubewahren ist dann genau diese
> Datei, unverändert.

Was paper-werk dazu beiträgt, und was nicht:

- Das XML wird beim Festschreiben **einmal** erzeugt und mit
  SHA-256-Prüfsumme abgelegt; `manage.py pruefe_belegarchiv` rechnet sie nach.
- Ins Archiv (Paperless) gelangt es **eingebettet im PDF**, weil Paperless
  kein XML annimmt. Das PDF ist dort der Anker.
- Zum Steuerberater bringt es der Kanal **`duo_paperwerk`** (in
  `pw_config` unter `steuer_kanal`; Workflow `sub-duo-versand-paperwerk`,
  in `workflows.list` mit `;true` eintragen): Bei XRechnung hängt er das
  XML als zweiten Anhang an die Mail mit dem PDF. Dafür braucht n8n in
  `pw_config` den Schlüssel `paperwerk_url` (Docker-Servicename, z. B.
  `http://paper-werk-app:8000`) und die Credential „Header Auth paper-werk“
  (`Token <Schlüssel des Dienstzugangs>`, Gruppe „Faktura Dienst“). Der
  Kanal `duo` bleibt für Paperless ohne paper-werk und schickt nur das PDF,
  ebenso StB-Zip und sevDesk.
- **Ob die Ablage als revisionssicher gilt, entscheidet nicht paper-werk**,
  sondern wie der Betrieb aufbewahrt. Das klärt der Kunde mit seinem
  Steuerberater, am besten schriftlich, bevor die erste Rechnung nur als XML
  hinausgeht.

Mit dem Steuerberater außerdem zu klären: die **Neuausstellung** einer
vom Portal abgewiesenen E-Rechnung unter derselben Nummer (Vorlage der
Verfahrensdokumentation, Abschnitt 2.3a) und die **Steuerfälle** der Kunden
(§ 13b, EU, Drittland; Abschnitt 2.7).

Einzutragen vor dem ersten Versand, damit die Pflichtangaben stimmen:

- **Firma** (im Admin): Telefon, E-Mail, IBAN, Anschrift, USt-IdNr. oder
  Steuernummer. Für XRechnung sind Telefon und E-Mail Pflicht.
- **Kunden, die XRechnung verlangen** (meist Behörden): Zustellweg
  „XRechnung“ und die **Leitweg-ID** als Käuferreferenz. Fehlt sie, lässt
  sich deren Rechnung nicht festschreiben.

Hintergrund und Formate: `paper-werk-app/docs/e-rechnung.md`.

---

## Troubleshooting

- **`jq: command not found` nach der Installation:** neues Terminalfenster
  öffnen; der PATH wird erst dann aktualisiert.
- **Container heißt anders als erwartet:** `./paper-werk compose ps --format
  '{{.Name}}'` im jeweiligen Ordner prüfen; der Name richtet sich nach dem
  Compose-Projektnamen (Standard = Ordnername, außer mit `-p` überschrieben).
- **Windows: ein Container startet nicht, `ports are not available: … bind:
  An attempt was made to access a socket in a way forbidden by its access
  permissions`** (bei uns aufgetreten bei Kopia auf Port 51515): Das ist
  **kein** belegter Port, sondern eine Portreservierung von Hyper-V/WSL -
  Windows hält ganze TCP-Bereiche für sich und verweigert das Binden. Prüfen
  (PowerShell):

  ```powershell
  netsh interface ipv4 show excludedportrange protocol=tcp
  Get-NetTCPConnection -LocalPort 51515 -ErrorAction SilentlyContinue
  ```

  Liegt der Port in einem ausgeschlossenen Bereich und meldet der zweite
  Befehl nichts, ist es die Reservierung. Zwei Lösungen:

  1. **WinNAT kurz durchstarten** (PowerShell als Administrator): schnell,
     kann aber nach einem Windows-Neustart wiederkommen:

     ```powershell
     net stop winnat
     .\paper-werk.cmd up
     net start winnat
     ```

  2. **Host-Port wechseln**, dauerhaft und ohne die Vorlage anzufassen: eine
     `compose.override.yml` in den Projektordner legen. `./paper-werk` nimmt sie
     von allein dazu:

     ```yaml
     services:
       kopia:
         ports: !override
           - "51616:51515"
     ```

     `!override` ist zwingend; ohne das hängt Compose die Ports-Listen
     aneinander, der alte Port bliebe drin und der Fehler käme wieder.

     **Die Datei heißt `compose.override.yml`, nicht
     `docker-compose.override.yml`.** Den zweiten Namen zieht Compose nur dann
     von allein mit, wenn niemand `-f` angibt, und `./paper-werk` gibt `-f` an.
     Deshalb nimmt es die Datei ausdrücklich dazu, unter diesem Namen.
     Container-intern ändert sich nichts, nur die URL wird
     `http://localhost:51616`. Die Setup-Skripte sind nicht betroffen, sie
     sprechen den Container über `docker exec` an, nicht über den Port.

  Bricht der Start mit diesem Fehler ab, bleiben nachfolgende Container in
  *Created* stehen (etwa `paperless`); ein erneutes
  `./paper-werk up` nach dem Fix startet sie mit.
- **Windows/Git Bash + Sonderzeichen oder Absturz beim Ausführen der
  Setup-Skripte:** sollte mit dem aktuellen Stand von `setup/`
  nicht mehr vorkommen (bekannte Git-Bash-Eigenheiten wurden dort gezielt
  abgefangen). Falls doch etwas hängt oder abstürzt: Terminal neu öffnen,
  den Befehl mit `> log.txt 2>&1` in eine Datei umleiten statt direkt
  anzuzeigen, und den Dateiinhalt prüfen.
- **Windows: „Wie möchten Sie diese Datei öffnen?"-Dialog beim Aufruf von
  `./setup.sh`** (danach blitzt kurz ein Fenster auf und schließt sich
  wieder): Der Aufruf lief in **PowerShell oder cmd**. Dort ist `.sh` kein
  ausführbarer Dateityp, Windows fragt deshalb nach einem Programm. Wählt man
  Git, startet das Skript in einem *eigenen* Fenster, das sich nach dem Ende
  sofort schließt; Ausgabe und Fehler sind nicht lesbar. Die Setup-Skripte
  brauchen eine Bash-Shell. Entweder Git Bash öffnen (Startmenü, oder im
  Repo-Ordner Rechtsklick → *Git Bash Here*) und dort arbeiten, mit Pfaden in der
  Form `/c/Projekte/...` statt `C:\Projekte\...`:

  ```bash
  cd /c/Pfad/zum/paper-werk/setup
  bash setup.sh --project ../config
  ```

  … oder ohne Shell-Wechsel direkt aus PowerShell heraus, dann bleibt die
  Ausgabe im aktuellen Fenster stehen:

  ```powershell
  & "C:\Program Files\Git\bin\bash.exe" -lc "cd /c/Pfad/zum/paper-werk/setup && bash setup.sh --project ../config"
  ```

- **`./setup.sh: Permission denied` (typischerweise nach `git clone` auf
  Linux/Mac):** Das Ausführungsrecht der `.sh`-Dateien
  kann bei einem Klon verloren gehen, wenn sie zuvor von einem
  Windows-Rechner aus committet wurden (NTFS kennt kein Unix-x-Bit, Git
  speichert es dann nicht). Am einfachsten `bash setup.sh …` aufrufen (braucht
  kein x-Bit), sonst einmalig selbst setzen:

  ```bash
  chmod +x setup.sh paperless/apply.sh n8n/apply.sh kopia/apply.sh
  ```

- **Postgres-Login schlägt fehl (`password authentication failed`):** meist
  ein Tippfehler zwischen `.env`-Passwort und einem bereits initialisierten
  `pgdata`-Ordner von einem vorherigen Versuch. Bei einem echten Neustart
  hilft nur ein leerer `pgdata`-Ordner (Achtung: Datenverlust, nur bei einer
  wirklich neuen/leeren Installation anwenden).
