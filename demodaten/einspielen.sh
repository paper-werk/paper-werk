#!/usr/bin/env bash
# Spielt einen Demobestand in eine frische Installation ein.
#
#   ./demodaten/einspielen.sh <installationsordner> <bestand>
#
# <bestand> ist ein Ordner unter demodaten/ oder ein Pfad; Pfade gelten vom
# Aufrufverzeichnis aus. Beispiel aus der Wurzel von paper-werk:
#
#   ./demodaten/einspielen.sh config-repos/paper-werk-config-dev elektro-hofmeister
#
# **Warum das kein Modul von setup.sh ist.** Demodaten dürfen niemals
# nebenbei mitlaufen. `setup.sh --project X` ohne Modulangabe fährt app,
# paperless, n8n und kopia. Wäre `demodaten` dabei, bekäme jede
# Kundeninstallation einen erfundenen Betrieb. Deshalb ein eigenes Skript,
# das man bewusst aufruft, wie starterpaket-zusammenstellen.sh oder
# kopia/sicherung.sh.
#
# **Genau ein Szenario: nackte, frische Installation.** Kein Nachladen, kein
# Zusammenführen. Auf einem gefüllten Bestand gibt es doppelte Kunden oder
# einen Abbruch; dann gehört die Datenbank vorher geleert.
#
# Der Bestand selbst steht in demodaten/, das Format ist dort in der
# 00-liesmich.md beschrieben. Dieses Skript kennt keinen Betrieb: Es bündelt
# die JSON-Dateien, legt sie in den Container und startet laden.py in der
# Django-Shell.

set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
source "$HIER/../setup/lib/common.sh"
require_cmd docker jq

[ $# -eq 2 ] || die "Aufruf: $0 <installationsordner> <bestand>"

export PROJECT_DIR
PROJECT_DIR="$(cd "$1" && pwd)" || die "Installationsordner nicht gefunden: $1"
if [ -d "$2" ]; then
  DEMODATEN="$(cd "$2" && pwd)"
elif [ -d "$HIER/$2" ]; then
  DEMODATEN="$HIER/$2"
else
  die "Bestand nicht gefunden: $2. Vorhanden: $(cd "$HIER" && ls -d */ | tr -d / | grep -vx __pycache__ | tr '\n' ' ')"
fi
load_conf

[ -n "${APP_CONTAINER:-}" ] \
  || die "APP_CONTAINER ist nicht gesetzt (setup.conf) - ohne ihn weiß dieses Skript nicht, welchen Container es meint."
docker inspect "$APP_CONTAINER" >/dev/null 2>&1 \
  || die "App-Container '$APP_CONTAINER' nicht gefunden (APP_CONTAINER in setup.conf prüfen)"

dateien=("$DEMODATEN"/*.json)
[ -e "${dateien[0]}" ] || die "Keine JSON-Dateien in $DEMODATEN"

log "Demodaten: $(basename "$DEMODATEN") (${#dateien[@]} Dateien)"

# Alle Dateien zu EINEM Dokument bündeln, in der Reihenfolge ihrer Namen -
# die Nummer im Dateinamen ist die Ladereihenfolge, und die ist fachlich
# zwingend (ohne Katalog kein Beleg).
#
# Ein Bündel statt einzelner Kopien, damit genau zwei docker-exec-Aufrufe
# nötig sind statt einem je Datei. Der Glob oben ist bereits sortiert.
buendel="$(for f in "${dateien[@]}"; do
  jq --arg n "$(basename "$f")" '{name: $n, inhalt: .}' "$f" \
    || die "Kein gültiges JSON: $f"
done | jq -s '.')"

# Über stdin in den Container und nicht als Argument: Git Bash auf Windows
# würde Umlaute in Argumenten für native Programme über die ANSI-Codepage
# umkodieren und dabei UTF-8 zerstören (dieselbe Begründung wie bei papi in
# lib/common.sh). Der Pfad im sh -c-String ist ein reiner Container-Pfad,
# deshalb MSYS_NO_PATHCONV.
printf '%s' "$buendel" \
  | MSYS_NO_PATHCONV=1 docker exec -i "$APP_CONTAINER" \
      sh -c 'cat > /tmp/demodaten.json'

# Und der Lader in den Container, dann ausführen.
#
# **Nicht `manage.py shell < laden.py`**, obwohl das kürzer wäre: Ohne
# ipython fällt Django auf eine INTERAKTIVE Konsole zurück, und die liest
# zeilenweise; eine Leerzeile innerhalb eines eingerückten Blocks beendet
# ihn dort. Ein Skript mit Klassen und Absätzen zerfällt so in Fragmente,
# und heraus kommt ein Haufen IndentationError zwischen scheinbar normaler
# Ausgabe.
#
# `shell -c` dagegen führt den String mit exec() aus: eine Übersetzung,
# ein Programm. Django steht dabei schon, kein eigenes django.setup() nötig.
MSYS_NO_PATHCONV=1 docker exec -i "$APP_CONTAINER" \
  sh -c 'cat > /tmp/laden.py' < "$HIER/laden.py"

if MSYS_NO_PATHCONV=1 docker exec "$APP_CONTAINER" \
     /app/.venv/bin/python manage.py shell \
     -c "exec(open('/tmp/laden.py', encoding='utf-8').read())"; then
  ok "Demodaten eingespielt."
else
  die "Der Lader hat abgebrochen - die Meldung steht darüber. Es wurde nichts angelegt (die Transaktion ist zurückgenommen)."
fi

# Die Aufräumarbeit gehört dazu: Ein Bestandsbündel im Container ist nach
# dem Lauf nur noch eine Datei, die niemand erwartet.
MSYS_NO_PATHCONV=1 docker exec "$APP_CONTAINER" rm -f /tmp/demodaten.json /tmp/laden.py
