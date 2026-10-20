#!/usr/bin/env bash
# Vergleicht die .env-Dateien einer Instanz mit den Vorlagen und meldet, was
# fehlt.
#
#   ./setup/env-abgleich.sh config
#
# ── Warum es dieses Skript gibt ───────────────────────────────────────────────
#
# Die .env-Dateien einer Instanz sind gitignored, weil sie Passwörter und
# Kundenadressen tragen. Das ist richtig und hat einen Preis: **Wenn eine Vorlage
# einen neuen Schlüssel bekommt, erfährt keine bestehende Instanz davon.**
# Sie läuft weiter wie bisher, und der Unterschied fällt erst auf, wenn
# jemand genau die Funktion braucht, die daran hängt.
#
# Beispiel: Fehlt PAPERLESS_CONSUMER_POLLING_INTERVAL, den die Vorlage als
# "PFLICHT auf Windows-Hosts" führt, zieht Paperless Papierbelege aus dem
# consume-Ordner nicht ein. Das fällt erst auf, wenn jemand den Ordner
# benutzt.
#
# **Verglichen werden nur die Schlüsselnamen, nie die Werte.** Ein Wert ist
# instanzspezifisch (Passwörter, Pfade, Adressen); dass er abweicht, ist der
# Normalfall und keine Meldung wert. Dass ein Schlüssel gar nicht vorkommt,
# ist dagegen fast immer ein Versehen.
#
# Auskommentierte Zeilen der Vorlage zählen als Angebot und nicht als
# Pflicht: Sie werden getrennt aufgeführt, damit man sie sieht, ohne dass
# jede Instanz sie haben müsste.

set -euo pipefail

HIER="$(cd "$(dirname "$0")" && pwd)"
WURZEL="$(cd "$HIER/.." && pwd)"
VORLAGEN="$WURZEL/config-template"

log()  { printf '\033[1;34m[abgleich]\033[0m %s\n' "$*"; }
fehlt(){ printf '\033[1;33m  fehlt:\033[0m   %s\n' "$*"; }
tipp() { printf '\033[0;36m  Angebot:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fehler]\033[0m %s\n' "$*" >&2; exit 1; }

PROJEKT="${1:-}"
[ -n "$PROJEKT" ] || die "Aufruf: $0 <projektordner>"
[ -d "$PROJEKT" ] || die "Projektordner nicht gefunden: $PROJEKT"
PROJEKT="$(cd "$PROJEKT" && pwd)"

schluessel()      { grep -oE '^[A-Z][A-Z0-9_]*=' "$1" 2>/dev/null | tr -d '=' | sort -u; }
schluessel_aus()  { grep -oE '^# *[A-Z][A-Z0-9_]*=' "$1" 2>/dev/null \
                      | sed -E 's/^# *//; s/=$//' | sort -u; }

gefunden=0
offen=0

for vorlage in "$VORLAGEN"/.env*.example; do
  name="$(basename "$vorlage" .example)"
  ziel="$PROJEKT/$name"

  if [ ! -f "$ziel" ]; then
    log "$name — in der Instanz nicht vorhanden"
    continue
  fi

  gefunden=$((gefunden + 1))
  pflicht="$(comm -23 <(schluessel "$vorlage") <(schluessel "$ziel"))"
  angebot="$(comm -23 <(schluessel_aus "$vorlage") <(schluessel "$ziel"))"

  if [ -z "$pflicht" ] && [ -z "$angebot" ]; then
    log "$name — vollständig"
    continue
  fi

  log "$name"
  for k in $pflicht; do fehlt "$k"; offen=$((offen + 1)); done
  for k in $angebot; do tipp "$k"; done
done

echo
[ "$gefunden" -gt 0 ] || die "Keine .env-Datei der Instanz gefunden - stimmt der Projektordner?"

if [ "$offen" -gt 0 ]; then
  log "$offen Schlüssel fehlen. Die Begründung steht jeweils als Kommentar"
  log "in der Vorlage unter config-template/ - dort nachlesen, bevor"
  log "etwas übernommen wird: Nicht jeder Schlüssel passt zu jedem Host."
else
  log "Nichts fehlt. Was als Angebot aufgeführt ist, steht in der Vorlage"
  log "auskommentiert und gilt nicht überall - siehe die Kommentare dort."
fi
