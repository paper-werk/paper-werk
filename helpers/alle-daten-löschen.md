# Komplett-Reset aller Daten einer Installation

⚠️ **Datenverlust.** Löscht Dokumente, Datenbank und n8n-Workflows einer
Installation vollständig. Nur für Test- oder wirklich neue Installationen –
bei Kundendaten vorher einen Kopia-Snapshot ziehen und dessen
Wiederherstellbarkeit prüfen (siehe
[docs/kopia-backblaze.md](../docs/kopia-backblaze.md)).

Die `docker compose`-Befehle laufen über `./paper-werk compose <name> ...` aus der
Repo-Wurzel - es kennt die Compose-Dateien der Installation. Die übrigen
Befehle (Pfade aus `.env`, `rm -rf`) im jeweiligen Projektordner
(`config/` oder `config-repos/paper-werk-config-<name>/`) ausführen.

## Variante A: Stack mit Named Volumes (Standard)

Ein Befehl genügt – `-v` entfernt die Volumes des Compose-Projekts mit:

```bash
./paper-werk down <name> -v
```

Danach legt `./paper-werk up <name>` alles frisch an.

## Variante B: Stack mit Bind-Mounts (ältere Installationen)

Hier liegen die Daten in Host-Ordnern unter `PAPERLESS_DATA_ROOT` bzw.
`KOPIA_DATA_ROOT`; `down -v` räumt sie deshalb **nicht** ab.

```bash
./paper-werk down <name>

# Pfade aus .env in die Shell holen, statt sie abzutippen
set -a; . ./.env; set +a
echo "$PAPERLESS_DATA_ROOT" "$KOPIA_DATA_ROOT"   # kontrollieren, bevor gelöscht wird!

sudo rm -rf "$PAPERLESS_DATA_ROOT"/{data,media,export,consume,pgdata,redisdata,n8ndata}
```

Der Kopia-Ordner (`$KOPIA_DATA_ROOT`) bleibt bewusst stehen – dort liegt das
Backup-Repository. Nur löschen, wenn auch die Sicherungen weg sollen.

Verzeichnisse wieder anlegen (Compose braucht sie für die Bind-Mounts):

```bash
mkdir -p "$PAPERLESS_DATA_ROOT"/{data,media,export,consume,pgdata,redisdata,n8ndata,hfcache}
mkdir -p "$KOPIA_DATA_ROOT"/{config,cache,repository,tmp}
ls "$PAPERLESS_DATA_ROOT"
```

## Portainer statt Kommandozeile

Stack Details → *Stop this Stack* → *Delete this Stack*, dann unter *Volumes*
die zum Stack gehörenden (als *Unused* markierten) Volumes löschen. Die
Bind-Mount-Ordner aus Variante B muss man trotzdem von Hand entfernen.
