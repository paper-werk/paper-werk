#!/usr/bin/env bash
# Spielt das Paperless-Starterpaket ein: Tags, Dokumenttypen, Custom Fields,
# Speicherpfade, Korrespondenten, Arbeitsabläufe (Workflows) und gespeicherte
# Ansichten aus paperless/starterpaket/*.json.
#
# Idempotent: Objekte werden über ihren Namen erkannt; vorhandene werden
# übersprungen, nie überschrieben. (Update bestehender Objekte: siehe
# "Ausbaustufen" im README.)
#
# Jede Seed-Datei ist optional: fehlt sie, wird der Schritt übersprungen. Damit
# laufen ältere Projektordner weiter, die correspondents.json/saved_views.json
# noch nicht haben.

set -euo pipefail
cd "$(dirname "$0")/.."
source lib/common.sh
load_conf
require_cmd curl jq

[ -n "${PAPERLESS_TOKEN:-}" ] || die "PAPERLESS_TOKEN fehlt in setup.conf"
SEED_DIR="$PROJECT_DIR/einstellungen/paperless/starterpaket"

paperless_bereit 30 2 || die "Paperless antwortet nicht (PAPERLESS_CONTAINER/PAPERLESS_URL in setup.conf prüfen)"

# Liefert für einen Endpunkt eine Name→ID-Map als JSON-Objekt.
# Zweites Argument: Feld, das als Name dient (Default "name"; /api/users/
# hat stattdessen "username").
fetch_map() {
  papi GET "/api/$1/?page_size=1000" \
    | jq --arg k "${2:-name}" '[.results[] | { (.[$k]): .id }] | add // {}'
}

# Prüft eine optionale Seed-Datei. Rückgabe 1 = nicht vorhanden (Schritt
# überspringen), Abbruch bei vorhandener, aber kaputter Datei.
seed_ready() {
  local endpoint="$1" seed="$2"
  if [ ! -f "$seed" ]; then
    log "$endpoint: keine Seed-Datei ($(basename "$seed")) - übersprungen"
    return 1
  fi
  jq empty "$seed" 2>/dev/null || die "Seed-Datei nicht lesbar oder kein gültiges JSON: $seed"
}

# Liefert die anzulegenden Objekte einer Seed-Datei, eines je Zeile.
#
# Übergangen wird dabei der reine Kommentarblock, den mehrere Seed-Dateien als
# erstes Array-Element führen ({ "_kommentar": "…" } ohne weitere Felder). Er
# ist Dokumentation, kein Objekt: Ohne diese Filterung bleibt nach dem
# del(._kommentar) unten ein leeres {} übrig, die API antwortet mit 400, und
# der Lauf bricht wegen set -e mitten im Starterpaket ab. Ein Paperless-Objekt
# ohne "name" gibt es nicht, das Kriterium trennt also sauber.
seed_items() {
  jq -c '.[] | select(has("name"))' "$1"
}

# Legt alle Objekte aus einer Seed-Datei an, sofern der Name noch nicht existiert.
ensure_objects() {
  local endpoint="$1" seed="$2" existing name obj
  seed_ready "$endpoint" "$seed" || return 0
  existing=$(fetch_map "$endpoint")
  while read -r obj; do
    name=$(jq -r '.name' <<<"$obj")
    if jq -e --arg n "$name" 'has($n)' <<<"$existing" >/dev/null; then
      log "$endpoint: '$name' existiert - übersprungen"
    else
      papi POST "/api/$endpoint/" "$(jq -c 'del(._kommentar)' <<<"$obj")" >/dev/null
      ok "$endpoint: '$name' angelegt"
    fi
  done < <(seed_items "$seed")
}

# Reihenfolge ist bindend: Arbeitsabläufe und Ansichten referenzieren diese
# Objekte per Name, die Auflösung unten braucht sie also bereits angelegt.
ensure_objects tags           "$SEED_DIR/tags.json"
ensure_objects document_types "$SEED_DIR/document_types.json"
ensure_objects custom_fields  "$SEED_DIR/custom_fields.json"
ensure_objects storage_paths  "$SEED_DIR/storage_paths.json"
ensure_objects correspondents "$SEED_DIR/correspondents.json"

# Name→ID-Maps für die beiden Auflöser weiter unten. Nutzer und Gruppen sind
# NICHT Teil des Starterpakets (Paperless legt sie nicht per API-Seed an); sie
# müssen vorher existieren, sonst bricht die Auflösung mit klarer Meldung ab.
tags_map=$(fetch_map tags)
dt_map=$(fetch_map document_types)
sp_map=$(fetch_map storage_paths)
cf_map=$(fetch_map custom_fields)
corr_map=$(fetch_map correspondents)
user_map=$(fetch_map users username)
group_map=$(fetch_map groups)

# ── Arbeitsabläufe ───────────────────────────────────────────────────────────
# In workflows.json stehen Tags, Dokumenttypen, Speicherpfade, Custom Fields,
# Korrespondenten, Nutzer und Gruppen als NAMEN; hier werden sie in IDs
# aufgelöst (schlägt fehl, wenn ein referenzierter Name nicht existiert).
#
# Rückwärtskompatibel: Aufgelöst wird nur, was als String dasteht. Zahlen
# gehen unverändert durch, ältere workflows.json mit rohen IDs funktionieren
# also weiter.
if seed_ready workflows "$SEED_DIR/workflows.json"; then
  existing_wf=$(fetch_map workflows)
  while read -r wf; do
    name=$(jq -r '.name' <<<"$wf")
    if jq -e --arg n "$name" 'has($n)' <<<"$existing_wf" >/dev/null; then
      log "workflows: '$name' existiert - übersprungen"
      continue
    fi
    resolved=$(jq -c \
      --argjson tags "$tags_map" \
      --argjson dts "$dt_map" \
      --argjson sps "$sp_map" \
      --argjson cfs "$cf_map" \
      --argjson corrs "$corr_map" \
      --argjson users "$user_map" \
      --argjson groups "$group_map" \
      -f paperless/resolve-workflow.jq <<<"$wf")
    papi POST "/api/workflows/" "$resolved" >/dev/null
    ok "workflows: '$name' angelegt"
  done < <(seed_items "$SEED_DIR/workflows.json")
fi

# ── Gespeicherte Ansichten ───────────────────────────────────────────────────
# Auch hier stehen Tags, Dokumenttypen usw. als NAMEN, aber in
# filter_rules[].value, wo der Feldname nichts über den Bezug verrät. Welcher
# rule_type worauf zeigt, steht in paperless/resolve-saved-view.jq.
#
# Ansichten gehören in Paperless immer einem Nutzer. Ohne "owner" ordnet die API
# sie dem Token-Inhaber zu (bei Einzelplatz-Installationen das Gewünschte);
# steht dort ein Benutzername, wird er aufgelöst.
#
# ── Zur Sichtbarkeit in der Seitenleiste ───────────────────────────────────
# "show_in_sidebar" in saved_views.json ist eine ABSICHT, kein API-Feld: Seit
# Paperless 3.x (hier geprüft an 3.0.5) gehört die Sichtbarkeit nicht mehr zur
# Ansicht, sondern zu den UI-Einstellungen des Nutzers, dort unter
# settings.saved_views.sidebar_views_visible_ids. Ein "show_in_sidebar" im
# POST-Body wird von DRF stillschweigend verworfen; resolve-saved-view.jq
# nimmt es deshalb heraus, und die IDs werden unten gesammelt und in einem
# Zug in die ui_settings geschrieben.
#
# Ohne diesen Schritt legt das Setup die Ansichten zwar an, aber sie stehen
# in keiner Seitenleiste, und der Kunde sieht nach dem ersten Login nichts.
if seed_ready saved_views "$SEED_DIR/saved_views.json"; then
  existing_sv=$(fetch_map saved_views)
  declare -a sidebar_ids=()
  while read -r sv; do
    name=$(jq -r '.name' <<<"$sv")
    sichtbar=$(jq -r '.show_in_sidebar // false' <<<"$sv")
    if jq -e --arg n "$name" 'has($n)' <<<"$existing_sv" >/dev/null; then
      log "saved_views: '$name' existiert - übersprungen"
      # Die Sichtbarkeit wird trotzdem nachgezogen: Sie steht nicht an der
      # Ansicht, sondern beim Nutzer; eine bestehende Ansicht kann also
      # unsichtbar sein, obwohl das Anlegen längst geklappt hat.
      if [ "$sichtbar" = "true" ]; then
        sidebar_ids+=("$(jq -r --arg n "$name" '.[$n]' <<<"$existing_sv")")
      fi
      continue
    fi
    resolved=$(jq -c \
      --argjson tags "$tags_map" \
      --argjson dts "$dt_map" \
      --argjson sps "$sp_map" \
      --argjson cfs "$cf_map" \
      --argjson corrs "$corr_map" \
      --argjson users "$user_map" \
      -f paperless/resolve-saved-view.jq <<<"$sv")
    if ! jq -e 'has("show_in_sidebar")' <<<"$sv" >/dev/null; then
      warn "saved_views: '$name' ohne show_in_sidebar - die Ansicht wird angelegt, erscheint aber in keiner Seitenleiste."
    fi
    antwort=$(papi POST "/api/saved_views/" "$resolved")
    ok "saved_views: '$name' angelegt"
    [ "$sichtbar" = "true" ] && sidebar_ids+=("$(jq -r '.id' <<<"$antwort")")
  done < <(seed_items "$SEED_DIR/saved_views.json")

  # Ein einziger Schreibvorgang für alle, weil die ui_settings kein
  # Teil-Update kennen; jeder POST ersetzt den ganzen Block.
  #
  # Gelesen wird vorher der Ist-Stand, und die neuen IDs kommen per `unique`
  # dazu statt an seine Stelle: Was der Betrieb selbst eingerichtet oder
  # ausgeblendet hat, bleibt. Ein zweiter Lauf ändert deshalb nichts mehr.
  #
  # ${arr[@]+"${arr[@]}"} wegen Bash 3.2 auf macOS; dort bricht die
  # Expansion eines leeren Arrays unter `set -u` ab (siehe n8n/apply.sh).
  if [ ${#sidebar_ids[@]} -gt 0 ]; then
    ids_json=$(printf '%s\n' ${sidebar_ids[@]+"${sidebar_ids[@]}"} \
      | jq -R 'select(length > 0) | tonumber' | jq -s 'unique')
    ui_ist=$(papi GET "/api/ui_settings/")
    ui_neu=$(jq -c --argjson ids "$ids_json" '
      {settings: (.settings
        | .saved_views = ((.saved_views // {})
          | .sidebar_views_visible_ids =
              (((.sidebar_views_visible_ids // []) + $ids) | unique)))}' \
      <<<"$ui_ist")
    papi POST "/api/ui_settings/" "$ui_neu" >/dev/null
    ok "Seitenleiste: $(jq 'length' <<<"$ids_json") Ansicht(en) sichtbar."
  fi
fi

ok "Paperless-Starterpaket eingespielt."
