#!/usr/bin/env bash
# Prüft, ob workflows.list und die Workflow-Dateien noch zueinander passen.
#
#   ./setup/n8n/liste-pruefen.sh [liste]
#
# Ohne Argument wird config-template/einstellungen/n8n/workflows.list.example geprüft.
#
# ── Warum es dieses Skript gibt ───────────────────────────────────────────────
#
# Die workflows.list steht neben den Workflow-Dateien und kann von ihnen
# abweichen. Zwei Fehlerbilder:
#
# - Die Liste nennt eine Datei, die umbenannt wurde. Wegen `set -e` bricht
#   der Import dort ab, und alle folgenden Workflows fehlen.
# - Ein Sub-Workflow, den gelistete Workflows aufrufen, fehlt in der Liste.
#   Die Aufrufer werden importiert und scheitern beim ersten Lauf, weil die
#   Workflow-ID in dieser n8n-Instanz nicht existiert. Auf bestehenden
#   Anlagen fällt das nicht auf, wenn der Sub dort von Hand importiert wurde.
#
# Dieses Skript stellt sie gegenüber, vor dem
# Ausrollen, nicht danach.

set -euo pipefail

HIER="$(cd "$(dirname "$0")" && pwd)"
WURZEL="$(cd "$HIER/../.." && pwd)"
LISTE="${1:-$WURZEL/config-template/einstellungen/n8n/workflows.list.example}"

log()  { printf '\033[1;34m[liste]\033[0m %s\n' "$*"; }
fehl() { printf '\033[1;31m  %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[fehler]\033[0m %s\n' "$*" >&2; exit 1; }

[ -f "$LISTE" ] || die "Liste nicht gefunden: $LISTE"
command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 \
    || die "python wird gebraucht (liest die Workflow-JSON)"
PY="$(command -v python3 || command -v python)"

cd "$WURZEL"

# ── 1. Steht jede gelistete Datei auch da? ──────────────────────────────────
fehlt=0
while IFS=';' read -r datei _; do
  datei="$(printf '%s' "$datei" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  case "$datei" in ''|\#*) continue;; esac
  if [ ! -f "$datei" ]; then fehl "Datei fehlt: $datei"; fehlt=$((fehlt + 1)); fi
done < "$LISTE"

# ── 2. Ruft ein gelisteter Workflow einen auf, der nicht gelistet ist? ──────
offen="$("$PY" - "$LISTE" <<'PYEOF'
import json, sys
from pathlib import Path

liste = Path(sys.argv[1])
pfade = []
for zeile in liste.read_text(encoding='utf-8').splitlines():
    zeile = zeile.strip()
    if zeile and not zeile.startswith('#'):
        pfade.append(zeile.split(';')[0].strip())

ids = set()
for pfad in pfade:
    p = Path(pfad)
    if p.exists():
        try:
            ids.add(json.loads(p.read_text(encoding='utf-8')).get('id'))
        except Exception:
            pass

for pfad in pfade:
    p = Path(pfad)
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding='utf-8'))
    for n in d.get('nodes', []):
        if 'xecuteWorkflow' not in n.get('type', ''):
            continue
        w = n.get('parameters', {}).get('workflowId', {})
        wid = w.get('value') if isinstance(w, dict) else w
        name = w.get('cachedResultName') if isinstance(w, dict) else '?'
        if wid and wid not in ids:
            print(f'{p.name} ruft {name} ({wid}) auf - nicht in der Liste')
PYEOF
)"

if [ -n "$offen" ]; then
  printf '%s\n' "$offen" | while read -r z; do fehl "$z"; done
  fehlt=$((fehlt + 1))
fi

echo
if [ "$fehlt" -eq 0 ]; then
  log "Liste und Dateien passen zusammen."
else
  die "Die Liste passt nicht zu den Dateien - siehe oben.
     Ein Import würde abbrechen oder Workflows anlegen, die beim Lauf scheitern."
fi
