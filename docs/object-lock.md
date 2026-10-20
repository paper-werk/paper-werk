# Object Lock: Backup gegen Ransomware härten

Anleitung für Backblaze B2 und Kopia, durchgeführt und verifiziert auf einer
Testinstallation unter Docker Desktop und einer Produktivinstallation.

Ergänzt [kopia-backblaze.md](kopia-backblaze.md),
wo Einrichtung, Restore-Tests und die Migration von `b2` auf `s3` stehen.

## Warum

Das Backup ist ein **Push-Ziel**: Der gesicherte Rechner hat selbst Schreib- und
Löschrecht darauf. Wer Root auf dem Docker-Host erlangt, findet

- den Zugangsschlüssel im Klartext in `/app/config/repository.config`
- das Repository-Passwort in `.env.kopia`

und kann damit **Originaldaten und Sicherung in einem Zug zerstören**. Eine
Cloud-Ablage schützt gegen Brand, Diebstahl und Plattendefekt, gegen einen
Verschlüsselungstrojaner nicht. Eine USB-Platte am selben Rechner genauso wenig.

Dagegen hilft nur Unveränderlichkeit auf Speicherseite: Ein gesperrter Blob
lässt sich für die eingestellte Frist nicht löschen, auch nicht mit gültigem
Schlüssel.

## Voraussetzungen

### 1. Bucket mit File Lock

Beim Anlegen im Web-UI aktivieren oder nachträglich per API. **Nicht mehr
abschaltbar**.

```bash
# nachträglich aktivieren (braucht writeBuckets)
POST /b2api/v2/b2_update_bucket
{"accountId": "...", "bucketId": "...", "fileLockEnabled": true}
```

Prüfen: `b2_list_buckets` → `"isFileLockEnabled": true`

### 2. Ein Key mit genau diesen sieben Capabilities

```json
["listBuckets","listFiles","readFiles","writeFiles","deleteFiles",
 "readFileRetentions","writeFileRetentions"]
```

| Capability | wofür |
|------------|-------|
| `listBuckets`, `listFiles` | Repository finden und Blobs auflisten |
| `readFiles` | Restore und Deduplizierung |
| `writeFiles` | Snapshots schreiben |
| `deleteFiles` | Maintenance, damit ausrotierte Blobs verschwinden |
| `writeFileRetentions` | Sperre beim Hochladen setzen |
| `readFileRetentions` | Sperrstatus lesen, um Verlängerung zu entscheiden |

**`bypassGovernance` darf NICHT dabei sein**: Diese Berechtigung hebelt den
gesamten Schutz aus. Ein Key damit darf trotz Sperre löschen.

**Das Web-UI kann das nicht.** "Read and Write" vergibt dort **25 Capabilities**
inklusive `bypassGovernance`, `writeBuckets`, `writeBucketLifecycleRules`,
`writeBucketRetentions`. Gemessen beim Anlegen eines Buckets. Der Key
muss deshalb **per API** erzeugt werden:

```bash
POST /b2api/v2/b2_create_key
{"accountId": "<acc>", "keyName": "kopia-<instanz>",
 "bucketId": "<bucket-id>",
 "capabilities": ["listBuckets","listFiles","readFiles","writeFiles",
                  "deleteFiles","readFileRetentions","writeFileRetentions"]}
```

Der Schlüssel wird **nur einmal** zurückgegeben; sofort ins Passwortmanagement.

### 3. Ein temporärer Verwaltungsschlüssel

`b2_create_key` verlangt `writeKeys`, das ein bucket-beschränkter Key nicht
haben kann. Also im Web-UI einmalig einen unbeschränkten Key mit Read/Write
anlegen (bekommt `writeKeys`, `deleteKeys`, `listKeys`), damit alles erledigen -
und ihn danach **wieder löschen**. Er ist selbst das größte Risiko im Konto.

Ein Key kann sich selbst löschen. Gegenprobe: `b2_authorize_account` mit seinen
Daten muss danach `unauthorized` liefern.

## Ablauf

Reihenfolge ist wichtig: Erst den Umschlag senken, dann sperren, weil gesperrte
Blobs Platz kosten.

### Schritt 1: Regenerierbares ausschließen

```bash
kopia policy set /source/paper-werk \
  --add-ignore='/data/index' \
  --add-ignore='/data/llm_index' \
  --add-ignore='/data/log' \
  --add-ignore='/data/classification_model.pickle'
```

Bei einer Installation mit 2350 Dokumenten spart das 359 MB pro Snapshot.
Verhalten nach einem Restore: `kopia-backblaze.md`, Abschnitt „Ausgeschlossene
Daten“. Paperless baut den Suchindex beim Start selbst neu; nur
`document_llmindex rebuild` ist von Hand nötig.

### Schritt 2: Auf den neuen Key umstellen

Backblaze-Keys sind **unveränderlich**: Einem bestehenden Key lässt sich keine
Capability hinzufügen; es bleibt nur, einen neuen anzulegen und umzustellen. Ablauf mit
Einweg-Container: `kopia-backblaze.md`, „Neuverbindung: Endpunkt- oder Key-Wechsel“.

### Schritt 3: Retention einschalten

```bash
kopia repository set-parameters --retention-mode=GOVERNANCE --retention-period=7d
```

`kopia repository status` zeigt danach:

```text
Blob retention mode:     GOVERNANCE
Blob retention period:   168h0m0s
```

Kopia meldet „you must disconnect and re-connect all other Kopia clients" -
den Container also neu starten, damit der Server-Prozess die neuen Parameter
kennt.

`GOVERNANCE` lässt sich mit `bypassGovernance` umgehen (deshalb Voraussetzung 2),
`COMPLIANCE` nicht einmal von Backblaze selbst; dafür ist dort auch eine
versehentlich zu lang gesetzte Frist unwiderruflich.

### Schritt 4: Object Lock Extension aktivieren

**Das ist der Schritt, den man übersieht.** `set-parameters` sorgt nur dafür,
dass *neu geschriebene* Blobs eine Sperre bekommen. Ohne die Extension werden
bestehende Sperren nie verlängert. Nach Ablauf der Frist wären auch weiterhin
benötigte Blobs wieder löschbar, und der Schutz verpufft.

```bash
kopia maintenance set --extend-object-locks=true
```

Prüfen: `kopia maintenance info` → `Object Lock Extension: enabled`
(Standard ist `disabled`.)

Danach einmal die Full-Maintenance laufen lassen, damit auch die *bestehenden*
Blobs eine Sperre bekommen:

```bash
kopia maintenance run --full
```

## Verifikation

### Sind die Blobs gesperrt?

`b2_list_file_names` liefert pro Datei `fileRetention`. Ergebnis auf der
Produktivinstallation nach Schritt 4:

```text
gesperrt (governance): 242 Blobs
ohne Sperre          : {'_log': 16, 'k': 1}
```

Ungesperrt bleiben nur Kopias eigene Log-Blobs (`_log…`) und der
Konfigurationsblob (`kopia.repository`/`kopia.blobcfg`/`kopia.maintenance`) -
die müssen überschreibbar bleiben. **Alle Daten- (`p…`) und Metadatenblobs
(`q…`) sind gesperrt.**

### Hält die Sperre einem Löschversuch stand?

Auf der Testinstallation gegen einen gesperrten Blob mit dem Backup-Key durchgespielt:

```json
{"code": "access_denied", "message": "Access Denied", "status": 401}
```

Derselbe Key konnte kurz zuvor einen **ungesperrten** Blob problemlos löschen -
der Unterschied liegt also an der Sperre, nicht an fehlenden Rechten.

**Diesen Test nur auf einer Testinstanz machen.** Trifft man versehentlich einen
ungesperrten Blob, ist er wirklich weg und das Repository beschädigt (`kopia
snapshot verify` meldet dann `backed by missing blob`). Reparatur: betroffene
Snapshots löschen, `kopia maintenance run --full --safety=none`, neuen Snapshot
ziehen; die Quelldaten liegen noch auf der Platte.

## Fallstricke

- **Die Sperre gilt nur für Blobs, die nach dem Einschalten geschrieben
  wurden.** Wer sofort danach testet, erwischt leicht einen alten und hält den
  Schutz fälschlich für wirkungslos. Erst nach Schritt 4 plus Full-Maintenance
  ist der Bestand geschützt.
- **`Object Lock Extension` steht standardmäßig auf `disabled`** und wird von
  `set-parameters` nicht mitaktiviert. Ohne sie läuft der Schutz nach der
  eingestellten Frist einfach aus.
- **Beide Maintenance-Einstellungen hängen am Repository, nicht am Container.**
  Wird eine Instanz umbenannt (neuer Compose-Projektname → neuer
  `KOPIA_HOSTNAME`), zeigt der Maintenance-Owner weiter auf den alten Hostnamen -
  und die Wartung läuft nie wieder automatisch, ohne dass irgendetwas eine
  Fehlermeldung erzeugt. Nach jeder Umbenennung prüfen:

  ```bash
  kopia maintenance info          # Owner: root@<aktueller-hostname>?
  kopia maintenance set --owner=me
  ```

  Typischer Fall nach einem Umbau: Der Owner steht auf einem Hostnamen, den es
  nicht mehr gibt.
- **Ein Snapshot ohne Änderungen erzeugt keine neuen Datenblobs** („Created
  snapshot … in 0s"). Für einen Test mit frischen Blobs muss sich an der Quelle
  wirklich etwas geändert haben.
- **Die Frist lässt sich hochsetzen, aber nicht rückwirkend senken.** Wer mit
  14 Tagen startet und feststellt, dass es zu teuer wird, muss die vollen
  14 Tage abwarten. Deshalb mit 7 anfangen.
- **File Lock am Bucket ist nicht abschaltbar.** Vor dem Aktivieren sicher sein.

## Kosten

Gesperrte Blobs kann die Maintenance nicht ausrotieren; sie belegen für die
Dauer der Frist weiter Platz.

Gemessen auf der Produktivinstallation (Upload-Volumen je Tag, siehe
`kopia-backblaze.md`):
**127 MB/Tag** im Schnitt, Streuung 23-273 MB.

| Frist | zusätzlicher Speicher |
|-------|----------------------|
| 7 Tage | ca. 0,9 GB |
| 14 Tage | ca. 1,8 GB |
| 30 Tage | ca. 3,8 GB |

Der Ausschluss von `/data` (Schritt 1) senkt den Umschlag deutlich und macht
Object Lock damit erheblich billiger. Die beiden Maßnahmen gehören zusammen.

## Zielzustand einer Installation

| | |
|---|---|
| Endpoint | `s3.<region>.backblazeb2.com` |
| Key | auf den Bucket beschränkt |
| Capabilities | die sieben oben, ohne `bypassGovernance` |
| File Lock am Bucket | aktiv |
| Retention | GOVERNANCE, 168h |
| Object Lock Extension | enabled |
| Lifecycle-Regel | „keep only last version" (1 Tag) |
| `/data`-Ignore | aktiv |

Die Secrets stehen in `<projekt>/einstellungen/setup.conf` (gitignored) und im
Klartext in `/app/config/repository.config` im jeweiligen `kopia-config`-Volume.
Zusätzlich gehören sie extern gesichert. Ohne sie ist das Bucket nach einem
Totalverlust nicht mehr erreichbar.
