# Datensicherung mit Kopia auf Backblaze B2

Sicherung und Wiederherstellung einer Installation mit Kopia, Ziel ist ein
Bucket bei Backblaze B2 über dessen S3-kompatible API. Der Aufbau gilt für
jede Installation aus diesem Repo.

## Aufbau

- **Eine Quelle für den ganzen Stack:** `/source/paper-werk` im
  Kopia-Container. Darunter ist jedes gesicherte Volume nur lesend unter
  seinem Namen eingehängt, dazu der Installationsordner (`config/` mit
  `.env`-Dateien und Zertifikat) unter `/source/paper-werk/config`. Die Liste
  steht in `compose/docker-compose.yml`; `tests/test_compose.py` prüft, dass
  jedes Volume gesichert ist oder ausdrücklich ausgenommen.
- **Restore-Ziele:** Dieselben Volumes sind beschreibbar unter
  `/restore/paper-werk/<volume>` eingehängt. `config/` ist dort nicht
  dabei; zurück auf den Host geht sie über `kopia restore` in einen Ordner
  unter `/tmp` und `docker cp`.
- **Zeitplan:** Die nächtliche Sicherung löst Kopias eigener Zeitplan aus,
  bei laufenden Datenbanken. Policy (zstd, Uhrzeit aus
  `KOPIA_SNAPSHOT_TIME`, Ausschlüsse aus `einstellungen/kopia/ignore.rules`)
  setzt `setup/kopia/apply.sh`.
- **Vor Updates und Eingriffen** zieht `setup/kopia/sicherung.sh` einen
  Snapshot bei gestoppten Datenbanken; Begründung im Kopf des Skripts.
- **Überwachung:** `./paper-werk doctor` meldet einen letzten Snapshot, der
  älter als 26 Stunden ist.
- **Nach jedem Restore** in der App `manage.py pruefe_belegarchiv` ausführen.
  Es hält jeden festgeschriebenen Beleg gegen seine Datei und deren
  Prüfsumme.

## Backblaze

[Doku Backblaze](https://www.backblaze.com/docs)

### Bucket

Privat, Region EU. Direkt nach dem Anlegen die Lifecycle-Regel setzen
(Bucket → Lifecycle Settings → *"Keep only the last version of the file"*),
Begründung unter [Lifecycle-Regel](#lifecycle-regel). Backblaze räumt
asynchron auf, bei einem Bucket mit Daten dauert das bis zu einen Tag.

### Application Key

Einen Application Key über *"Add a new Application Key"* anlegen, keinen
Master Application Key: Dieser funktioniert mit der S3-API nicht.

Kopia braucht fünf Capabilities: `listBuckets`, `listFiles`, `readFiles`,
`writeFiles`, `deleteFiles`. Ohne `deleteFiles` kann die Maintenance
ausrotierte Blobs nicht löschen, und der Bucket wächst ohne Grenze.

Im Web-UI:

| Feld | Wert |
|------|------|
| Allow access to Bucket(s) | nur den Backup-Bucket |
| Type of Access | Read and Write |
| Allow List All Bucket Names | nicht ankreuzen |

Die Beschränkung auf den Bucket ist die wichtigste Einstellung. Der Key liegt
im Klartext auf dem Docker-Host; ohne Beschränkung kommt er an alle Buckets
des Kontos. Kontoweite Rechte wie `writeKeys`, `deleteKeys` oder
`deleteBuckets` kann ein bucket-beschränkter Key nicht bekommen.

„Read and Write“ im Web-UI vergibt 25 Capabilities, darunter
`writeBuckets`, `writeBucketLifecycleRules`, `writeBucketRetentions` und
`bypassGovernance`. `bypassGovernance` hebt Object Lock auf. Mit Object Lock
den Key deshalb über die API anlegen, mit sieben Capabilities (die fünf oben
und die beiden Retention-Rechte), ohne `bypassGovernance`:

```bash
# b2_create_key mit expliziter Liste
{"accountId": "...", "keyName": "kopia-<instanz>",
 "bucketId": "<bucket-id>",
 "capabilities": ["listBuckets","listFiles","readFiles","writeFiles",
                  "deleteFiles","readFileRetentions","writeFileRetentions"]}
```

Ohne Object Lock genügen die fünf; mit Object Lock scheitert Kopia ohne die
Retention-Rechte beim Setzen der Sperre. Ablauf und Prüfung:
[object-lock.md](object-lock.md). Die tatsächlichen Rechte eines Keys zeigt
`b2_authorize_account` unter `allowed`.

## Kopia

### Repository

Kopia verbindet sich über den S3-kompatiblen Endpunkt. Der eigene
`b2`-Provider von Kopia ist deprecated; dasselbe Bucket ist über beide
Zugriffsarten erreichbar.

Im Web-UI: Repository → Select Storage Type → **S3-Compatible Storage**:

| Feld | Wert |
|------|------|
| Bucket | Bucketname |
| Server Endpoint | `s3.eu-central-003.backblazeb2.com` (Region aus dem B2-Dashboard) |
| Access Key ID | die Key-ID des Application Keys |
| Secret Access Key | der Application Key |

Prefix leer lassen, dann das Repository-Passwort vergeben
(`KOPIA_PASSWORD` in `.env.kopia`). Ohne dieses Passwort sind die Daten im
Bucket nicht lesbar.

Auf der Kommandozeile:

```bash
kopia repository connect s3 \
  --bucket=<bucket> \
  --endpoint=s3.eu-central-003.backblazeb2.com \
  --access-key=<key-id> \
  --secret-access-key=<application-key>
```

Den Endpunkt zeigt das B2-Dashboard beim Bucket ("Endpoint"), die API liefert
ihn in `b2_authorize_account` als `s3ApiUrl`. Das Flag heißt `--access-key`.

### Policy

`setup/kopia/apply.sh` setzt die Policy der Quelle `/source/paper-werk`:
Kompression `zstd`, ein täglicher Snapshot zur Uhrzeit aus
`KOPIA_SNAPSHOT_TIME`, die Ausschlüsse aus
`einstellungen/kopia/ignore.rules`. Benachrichtigungen per Mail werden im
Kopia-Web-UI eingerichtet.

## Lifecycle-Regel

Löscht Kopia einen Blob, setzt Backblaze einen *Hide-Marker*; der Inhalt
bleibt als versteckte Version liegen und wird voll berechnet. Mit der
Vorgabe *"Keep all versions of the file"* bleibt er dauerhaft. Auf einer
Installation bestand ein Bucket von 9,86 GB zu 4,12 GB aus Blobs, die Kopia
noch referenzierte; 5,37 GB waren gelöschte und 0,37 GB überschriebene
Versionen. Kopia-seitige Maßnahmen (Retention, Maintenance) ändern daran
nichts.

Die Regel *"Keep only the last version of the file"* entspricht per API:

```json
[{"fileNamePrefix": "", "daysFromHidingToDeleting": 1, "daysFromUploadingToHiding": null}]
```

Kopia versioniert selbst über Snapshots und braucht die Dateiversionen von
B2 nicht. Nach einer versehentlichen Blob-Löschung bleibt ein Tag, um sie
über Backblaze zurückzuholen. Den Ist-Zustand zeigt `b2_list_file_versions`;
im Web-UI unter "Browse Files" mit eingeblendeten versteckten Dateien.

## Ausgeschlossene Daten

Gesichert werden alle Volumes außer `redisdata` (Warteschlange und Cache)
und Kopias eigenen. Innerhalb von `data/` (Paperless) schließt
`ignore.rules` Daten aus, die Paperless neu erzeugt und die sich täglich
vollständig ändern, also kaum deduplizieren:

```text
/data/index                       # Volltext-Suchindex (Tantivy)
/data/llm_index                   # Vektorindex der KI-Funktionen
/data/log                         # Anwendungslogs
/data/classification_model.pickle # trainiertes Klassifikationsmodell
```

Über zwölf Snapshots einer Installation mit 2350 Dokumenten verursachte
`data/` 1493 MB Überhang, `media/` dagegen 26 MB. `pgdata` bleibt gesichert:
Sein Überhang sind WAL-Segmente, die Postgres für die Crash-Recovery nach
einem Restore braucht.

Nach einem Restore:

| Bestandteil | Verhalten | zu tun |
|-------------|-----------|--------|
| PostgreSQL | automatische Crash-Recovery (`automatic recovery in progress`, `redo starts`), danach bereit | nichts |
| Dokumente und Metadaten | vollständig | nichts |
| Volltext-Suchindex | wird beim Containerstart neu gebaut (`[init-index] Checking search index...`) | nichts |
| `llm_index` | wird nicht neu gebaut, auch nicht mit `PAPERLESS_AI_ENABLED=true` | `document_llmindex rebuild` |
| `classification_model.pickle` | entsteht beim nächsten geplanten Training | nichts (oder `document_create_classifier`) |
| `data/log` | füllt sich im Betrieb | nichts |

```bash
./paper-werk compose exec paperless python3 manage.py document_llmindex rebuild
```

Der Neuaufbau dauert etwa eine Sekunde je Dokument und schickt jedes
Dokument zur Embedding-Berechnung an den konfigurierten Anbieter, mit den
entsprechenden API-Kosten. Ohne KI-Funktionen entfällt er.

## Wiederherstellung

### Einzelne Dateien

Fehlen Dokumente, ohne dass bekannt ist, welche, zeigt `kopia diff` den
Unterschied zwischen einem älteren und einem neuen Snapshot mit vollem Pfad
(`removed file ...`):

```bash
kopia diff <snapshot-alt> <snapshot-neu>
kopia restore <snapshot-alt>/media/documents/originals/<ordner>/<datei>.pdf \
  /restore/paper-werk/media/documents/originals/<ordner>/<datei>.pdf
```

Einzelne Dokumente haben keine Abhängigkeiten untereinander und lassen sich
deshalb einzeln zurückspielen.

### Datenbanken

Eine Datenbank immer vollständig zurückspielen (`pgdata` bzw.
`app-pgdata`), nie Teile wie `pg_wal`. Ein Snapshot einer laufenden Instanz
ist nur crash-konsistent; Postgres repariert ihn beim Start per WAL-Replay,
und das setzt einen in sich konsistenten Datenordner voraus. Ein Restore nur
von `pg_wal` endet mit `PANIC: could not locate a valid checkpoint record`.
Vor dem Restore den zugehörigen Datenbankdienst stoppen
(`paperless-db` bzw. `paper-werk-db`).

### Totalverlust

Außerhalb des Docker-Hosts vorzuhalten:

- `config/` der Installation, mit `.env.kopia` (`KOPIA_PASSWORD`).
- Bucket-Name, Key-ID und Application Key. Diese stehen nur in
  `kopia-config` (`/app/config/repository.config`) und gehen mit dem Host
  verloren; Backblaze zeigt einen Application Key nur beim Anlegen.

Ablauf:

```bash
./paper-werk compose up -d kopia     # nur Kopia
# im Kopia-Container:
kopia repository connect s3 --bucket=<bucket> \
  --endpoint=<endpoint> --access-key=<key-id> --secret-access-key=<key>
kopia snapshot list --all
kopia restore <snapshot-id>/pgdata     /restore/paper-werk/pgdata
kopia restore <snapshot-id>/app-pgdata /restore/paper-werk/app-pgdata
kopia restore <snapshot-id>/media      /restore/paper-werk/media
kopia restore <snapshot-id>/app-media  /restore/paper-werk/app-media
kopia restore <snapshot-id>/data       /restore/paper-werk/data
# ebenso n8ndata, consume, caddy-data, caddy-config
./paper-werk up                      # danach der Rest
```

Nur Kopia zuerst starten, weil Postgres auf einem leeren Volume sonst sofort
eine neue Datenbank anlegt, bevor der Restore hineinschreibt. Danach
`pruefe_belegarchiv` in der App und, mit KI-Funktionen,
`document_llmindex rebuild` in Paperless.

## Object Lock

Wer Root auf dem Docker-Host hat, findet Key und Repository-Passwort im
Klartext und kann Originaldaten und Sicherung löschen. Dagegen schützt eine
Sperre auf Seiten des Speichers. Anleitung mit Capabilities, Ablauf und
Prüfung: [object-lock.md](object-lock.md).

## Neuverbindung: Endpunkt- oder Key-Wechsel

Ein Wechsel von `b2` auf S3 oder auf einen neuen Key ist ein reiner
Verbindungswechsel: dasselbe Bucket, dieselben Daten.

**`hostname` und `username` müssen erhalten bleiben.** Sie bilden die
Snapshot-Quelle (`root@<kopia-hostname>:/source/paper-werk`). Ändern sie
sich, landen neue Snapshots unter einer neuen Quelle: Die Retention beginnt
bei null, die alte Historie verwaist, und der Maintenance-Owner passt nicht
mehr. Vorher `kopia repository status` festhalten und danach vergleichen.
Beim Verbinden außerdem `--description` und `--cache-directory` angeben,
sonst setzt Kopia Vorgaben und lädt den Cache neu.

1. In einer getrennten Config-Datei testen; die bestehende Verbindung bleibt
   unverändert:

   ```bash
   docker exec <kopia-container> kopia --config-file=/tmp/probe.config \
     repository connect s3 --bucket=<bucket> --endpoint=<endpoint> \
     --access-key=<key-id> --secret-access-key=<key> \
     --cache-directory=/tmp/probecache
   docker exec <kopia-container> kopia --config-file=/tmp/probe.config repository status
   ```

   Stimmt die `Unique ID` und ist die Snapshot-Historie vollständig, ist es
   dasselbe Repository.
2. Laufende Maintenance abwarten (`kopia maintenance info`).
3. `/app/config/repository.config` kopieren (Rollback).
4. Kopia stoppen und in einem Einweg-Container mit denselben Volumes neu
   verbinden; der Server-Modus verträgt kein `disconnect` im Betrieb:

   ```bash
   ./paper-werk compose stop kopia
   docker run --rm --hostname <kopia-hostname> -e KOPIA_PASSWORD \
     -v <projekt>_kopia-config:/app/config -v <projekt>_kopia-cache:/app/cache \
     kopia/kopia:latest repository disconnect
   docker run --rm --hostname <kopia-hostname> -e KOPIA_PASSWORD \
     -v <projekt>_kopia-config:/app/config -v <projekt>_kopia-cache:/app/cache \
     kopia/kopia:latest repository connect s3 \
       --bucket=<bucket> --endpoint=<endpoint> \
       --access-key=<key-id> --secret-access-key=<key> \
       --cache-directory=/app/cache --description=<bisherige-description>
   ./paper-werk compose start kopia
   ```

   Ohne `--hostname` nimmt Kopia die Container-ID als Hostname.

Hinweise:

- Das Image `kopia/kopia` hat `kopia` als ENTRYPOINT; im `docker run` steht
  deshalb direkt `repository connect ...`.
- `unable to remove cache directory: device or resource busy` beim
  `disconnect` ist harmlos: `/app/cache` ist ein Mountpoint, der Cache bleibt.
- `docker --env-file` entfernt keine Anführungszeichen. Das Passwort deshalb
  mit `docker exec <kopia-container> printenv KOPIA_PASSWORD` auslesen und
  per `-e KOPIA_PASSWORD` übergeben.
- `kopia maintenance run` läuft ohne Flag im Schnellmodus; das Gegenstück
  ist `--full`.

Prüfung danach: `kopia repository status`, `kopia policy list`,
`kopia snapshot list --all`, `kopia maintenance info`, ein Test-Restore einer
Datei und `kopia maintenance run --full`. Dass der Zeitplan schreibt, belegt
erst der nächste reguläre Snapshot.

Beim Key-Wechsel den alten Key erst löschen, wenn sicher ist, dass kein
anderes Backup im selben Konto ihn benutzt; Backblaze protokolliert nicht,
welcher Key welchen Bucket beschreibt. Beim Aufräumen nach der Key-ID gehen.
Ein Bucket lässt sich nur mit `deleteBuckets` löschen, also mit einem
kontoweiten Key: erst Bucket, dann Key. Beim Leeren im Web-UI alle Versionen
einblenden, sonst scheitert das Löschen mit "bucket not empty".

Gegenprobe für einen eng geschnittenen Key: Mit seinen Zugangsdaten zeigt
`b2_list_buckets` nur den eigenen Bucket; `b2_list_keys` und `b2_create_key`
enden mit HTTP 401.
