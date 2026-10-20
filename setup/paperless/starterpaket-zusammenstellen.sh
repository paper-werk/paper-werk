#!/usr/bin/env bash
# Stellt das Paperless-Starterpaket einer Installation zusammen: starterpakete/basis/
# plus optional eine Variante starterpakete/<variante>/, Ziel
# <installationsordner>/einstellungen/paperless/starterpaket/.
#
#   ./setup/paperless/starterpaket-zusammenstellen.sh <installationsordner> [variante]
#
# Beispiele:
#   ... config                                     # nur basis
#   ... config-repos/paper-werk-config-dev elektro # basis + elektro
#
# ── Warum es dieses Skript gibt ───────────────────────────────────────────────
#
# Eine Variante (etwa elektro) ergänzt das Basispaket.
#
# **Nicht als zweites vollständiges Paket.** Der Basissatz ist zu vier
# Fünfteln gewerkeneutral: Rechnung, Angebot, Vertrag, Kontoauszug hat jeder
# Betrieb. Schlimmer: Mehrere Tags und Custom Fields sind an n8n-Workflows und
# an paper-werk-app gekoppelt (angebot-offen, buchungsrelevant, mistral-ocr,
# Gesamtbetrag, Rechnungsnummer, Projekt). Stünden die in jeder Variante ein
# zweites Mal, wäre beim nächsten Workflow-Umbau eine der Listen veraltet -
# und niemand wüsste, welche.
#
# Eine Variante enthält deshalb **nur ihre Ergänzungen**, und dieses Skript
# fügt sie zum Basispaket. Dieselbe Regel wie beim Vorführbestand in
# paper-werk-app: Was mehrfach gebraucht wird, steht einmal da.
#
# Idempotent bleibt ohnehin apply.sh: Es legt nur an, was in Paperless noch
# nicht existiert, und überschreibt nie.

set -euo pipefail

HIER="$(cd "$(dirname "$0")" && pwd)"
WURZEL="$(cd "$HIER/../.." && pwd)"

log()  { printf '\033[1;34m[starterpaket]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[achtung]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[fehler]\033[0m %s\n' "$*" >&2; exit 1; }

command -v jq >/dev/null 2>&1 || die "jq wird gebraucht - siehe Kundeninstallation.md, Schritt 1."

PROJEKT="${1:-}"
VARIANTE="${2:-}"
[ -n "$PROJEKT" ] || die "Aufruf: $0 <projektordner> [variante]"
[ -d "$PROJEKT" ] || die "Projektordner nicht gefunden: $PROJEKT"
PROJEKT="$(cd "$PROJEKT" && pwd)"

BASIS="$WURZEL/starterpakete/basis"
[ -d "$BASIS" ] || die "Basispaket nicht gefunden: $BASIS"

if [ -n "$VARIANTE" ]; then
  ZUSATZ="$WURZEL/starterpakete/$VARIANTE"
  { [ "$VARIANTE" != "basis" ] && [ -d "$ZUSATZ" ]; } \
    || die "Variante '$VARIANTE' gibt es nicht. Vorhanden: $(cd "$WURZEL/starterpakete" && ls -d */ | tr -d / | grep -vx basis | tr '\n' ' ')"
else
  ZUSATZ=""
fi

ZIEL="$PROJEKT/einstellungen/paperless/starterpaket"
mkdir -p "$ZIEL"

DATEIEN=(correspondents custom_fields document_types saved_views storage_paths tags workflows)

for name in "${DATEIEN[@]}"; do
  basis="$BASIS/$name.json"
  ziel="$ZIEL/$name.json"

  if [ ! -f "$basis" ]; then
    warn "$name: im Basispaket nicht vorhanden - übersprungen"
    continue
  fi

  if [ -f "$ziel" ] && [ "${FORCE:-}" != "1" ]; then
    warn "$name.json steht schon im Projektordner - unberührt gelassen (FORCE=1 überschreibt)"
    continue
  fi

  zusatz=""
  [ -n "$ZUSATZ" ] && [ -f "$ZUSATZ/$name.json" ] && zusatz="$ZUSATZ/$name.json"

  if [ -z "$zusatz" ]; then
    cp "$basis" "$ziel"
    log "$name.json  (Basis, $(jq '[.[] | select(has("name"))] | length' "$ziel") Einträge)"
    continue
  fi

  # **Doppelte Namen sind ein Fehler in der Variante, kein Zufall.** apply.sh
  # legt jeden Namen nur einmal an; ein zweiter Eintrag desselben Namens
  # verschwindet also stillschweigend und mit ihm der Unterschied, um
  # dessentwillen er dastand. Deshalb hier abbrechen statt weitermachen.
  doppelt="$(jq -r -s '
      [.[0][], .[1][] | select(has("name")) | .name]
      | group_by(.) | map(select(length > 1) | .[0]) | join(", ")
    ' "$basis" "$zusatz")"
  if [ -n "$doppelt" ]; then
    die "$name: diese Namen stehen in Basis UND Variante '$VARIANTE': $doppelt
     Die Variante trägt nur Ergänzungen - was schon im Basispaket steht, dort streichen."
  fi

  jq -s 'add' "$basis" "$zusatz" > "$ziel"
  log "$name.json  (Basis + $VARIANTE, $(jq '[.[] | select(has("name"))] | length' "$ziel") Einträge)"
done

echo
if [ -n "$VARIANTE" ]; then
  log "Zusammengestellt: Basispaket + Variante '$VARIANTE' → $ZIEL"
else
  log "Zusammengestellt: Basispaket → $ZIEL"
fi
log "Die Korrespondenten sind Platzhalter - vor einer echten Installation ersetzen."
