#!/usr/bin/env bash
# Importiert die in n8n/workflows.list gelisteten Workflow-JSONs (aus dem
# Repo-Ordner n8n/) in die laufende n8n-Instanz.
#
# Erprobte Stolperfallen, die dieses Skript berücksichtigt:
#   - `n8n import:workflow` setzt 'active' immer auf false zurück und lässt
#     den Workflow "unpublished" (Spalte activeVersionId = null) → aktivieren
#     UND veröffentlichen muss danach per `n8n publish:workflow` erfolgen
#     (setzt active + activeVersionId atomar). Das ältere `update:workflow
#     --active=true` ist deprecated und setzt NUR die active-Spalte, nicht
#     activeVersionId → Workflow bleibt in der UI als "nicht published"
#     sichtbar, obwohl active=true (geprüft per SQLite-Direktabfrage).
#   - Die laufende n8n-Instanz sieht DB-Änderungen der CLI erst nach einem
#     Container-Restart → Reihenfolge: import → publish → restart → healthz.
#
# Idempotent, aber NICHT destruktiv: Ein Workflow, der in n8n schon existiert
# (gleiche ID), wird standardmäßig übersprungen statt überschrieben, weil sonst
# Einstellungen verloren gingen, die jemand direkt in der n8n-UI gemacht hat
# (Credentials zugewiesen, Nodes angepasst, aktiviert, ...). Mit --force
# (an setup.sh übergeben, hier als SETUP_FORCE) wird trotzdem überschrieben.

set -euo pipefail
cd "$(dirname "$0")/.."
source lib/common.sh
load_conf
require_cmd docker jq

force="${SETUP_FORCE:-false}"
MANIFEST="$PROJECT_DIR/einstellungen/n8n/workflows.list"
[ -f "$MANIFEST" ] || die "Manifest fehlt: $MANIFEST"

docker inspect "$N8N_CONTAINER" >/dev/null 2>&1 \
  || die "n8n-Container '$N8N_CONTAINER' nicht gefunden (N8N_CONTAINER in setup.conf prüfen)"

# ── Credentials (optional) ──────────────────────────────────────────────────
# n8n/credentials.json (gitignored, aus credentials.json.example). IDs sind
# dort bewusst fest und passen zu den credentials-Referenzen in den
# Workflow-Dateien, damit sie nach dem Import automatisch im Node vorausgewählt
# sind (kein manuelles Nachziehen in der UI). Läuft vor dem Workflow-Import,
# damit die Referenzen beim Import schon auflösbar sind. Gleiche
# Idempotenz-Logik wie bei Workflows: existierende ID wird übersprungen,
# --force überschreibt (z. B. um ein rotiertes Token nachzuziehen).
CREDENTIALS_FILE="$PROJECT_DIR/einstellungen/n8n/credentials.json"
if [ -f "$CREDENTIALS_FILE" ]; then
  jq empty "$CREDENTIALS_FILE" 2>/dev/null \
    || die "Seed-Datei nicht lesbar oder kein gültiges JSON: $CREDENTIALS_FILE"

  # tr -d '\r': docker exec und das native jq.exe liefern unter Git Bash CRLF.
  # Ohne das Strippen endet jede ID auf \r und `grep -qx` findet sie nicht mehr
  # → vorhandene Credentials würden bei jedem Lauf neu importiert und damit
  # überschrieben.
  MSYS_NO_PATHCONV=1 docker exec -u node "$N8N_CONTAINER" \
    n8n export:credentials --all --output=/tmp/setup-existing-creds.json >/dev/null 2>&1 || true
  existing_cred_ids=$(MSYS_NO_PATHCONV=1 docker exec -u node "$N8N_CONTAINER" \
    cat /tmp/setup-existing-creds.json 2>/dev/null | jq -r '.[]?.id // empty' 2>/dev/null \
    | tr -d '\r' || true)

  imported_creds=0
  skipped_creds=0
  while read -r cred; do
    cred_id=$(jq -r '.id // empty' <<<"$cred")
    cred_name=$(jq -r '.name' <<<"$cred")
    [ -n "$cred_id" ] || die "credentials.json: Eintrag '$cred_name' ohne 'id'-Feld"

    if [ "$force" != "true" ] && grep -qx "$cred_id" <<<"$existing_cred_ids"; then
      warn "n8n-Credential: '$cred_name' (id=$cred_id) existiert bereits - übersprungen (--force zum Überschreiben)"
      skipped_creds=$((skipped_creds + 1))
      continue
    fi

    MSYS_NO_PATHCONV=1 docker exec -i -u node "$N8N_CONTAINER" sh -c 'cat > /tmp/setup-import-cred.json' \
      <<<"$(jq -c 'del(._kommentar) | [.]' <<<"$cred")"
    MSYS_NO_PATHCONV=1 docker exec -u node "$N8N_CONTAINER" \
      n8n import:credentials --input=/tmp/setup-import-cred.json >/dev/null
    ok "n8n-Credential: '$cred_name' (id=$cred_id) importiert"
    imported_creds=$((imported_creds + 1))
  done < <(jq -c '.[]' "$CREDENTIALS_FILE")
  log "Credentials: $imported_creds importiert, $skipped_creds übersprungen."

  # Der Paperless-Token steht an ZWEI Stellen: in setup.conf (für diese
  # Skripte) und in der Credential "Header Auth paperless" (für die Workflows).
  # Laufen sie auseinander, ist der Schaden still und schwer zu finden:
  # Paperless feuert den Webhook und entfernt den Kommando-Tag, n8n scheitert
  # mit "Authorization failed"; am Dokument selbst sieht man nur, dass nichts
  # passiert ist. Typischer Fall: eine credentials.json aus einer früheren
  # Installation mit deren Token, während die frische Paperless-Datenbank
  # einen neuen hat.
  cred_token=$(jq -r '[.[] | select((.data.value? // "") | startswith("Token "))][0].data.value // empty' \
                  "$CREDENTIALS_FILE" | sed 's/^Token //')
  if [ -n "$cred_token" ] && [ -n "${PAPERLESS_TOKEN:-}" ] && [ "$cred_token" != "$PAPERLESS_TOKEN" ]; then
    warn "Der Paperless-Token in credentials.json weicht von dem in setup.conf ab."
    warn "Die n8n-Workflows werden sich damit an Paperless nicht anmelden können"
    warn "(Symptom: Kommando-Tag verschwindet, aber am Dokument passiert nichts)."
    warn "Token in einstellungen/n8n/credentials.json angleichen, dann:"
    warn "  bash setup.sh --project <projektordner> n8n --force"
  fi
else
  log "n8n/credentials.json nicht vorhanden - übersprungen (optional, siehe credentials.json.example)."
fi

# Vorhandene Workflow-IDs einmal vorab abfragen (Format je Zeile "id|name").
# tr -d '\r' wie oben. Hier fällt das CR zwar nicht auf (cut schneidet es mit
# dem Namen ab), aber verlassen sollte man sich darauf nicht.
existing_ids=$(docker exec -u node "$N8N_CONTAINER" n8n list:workflow 2>/dev/null \
  | tr -d '\r' | cut -d'|' -f1)

# Und daneben: welche davon sind bereits aktiv+veröffentlicht. Gebraucht wird
# das unten beim Überspringen; die Begründung steht dort.
active_ids=$(docker exec -u node "$N8N_CONTAINER" n8n list:workflow --active=true 2>/dev/null \
  | tr -d '\r' | cut -d'|' -f1)

imported=0
skipped=0
declare -a activate_ids=()

while IFS=';' read -r path active; do
  # CRLF-Reste entfernen, Kommentare/Leerzeilen überspringen
  path="${path//$'\r'/}"; active="${active//$'\r'/}"
  case "$path" in ''|\#*) continue ;; esac
  path="$(echo "$path" | xargs)"; active="$(echo "$active" | xargs)"
  file="$REPO_ROOT/$path"
  [ -f "$file" ] || die "Workflow-Datei fehlt: $file"

  wf_id=$(jq -r '.id // empty' "$file")
  [ -n "$wf_id" ] || die "Workflow-JSON ohne 'id'-Feld: $path"

  if [ "$force" != "true" ] && grep -qx "$wf_id" <<<"$existing_ids"; then
    warn "n8n: '$path' (id=$wf_id) existiert bereits - übersprungen (--force zum Überschreiben)"
    skipped=$((skipped + 1))
    # ABER: die Veröffentlichung darf am Überspringen nicht hängenbleiben.
    #
    # Ein bloßes `continue` übersprünge die Zeile weiter unten, die den
    # Workflow in activate_ids legt. Bei einem zweiten Lauf (die
    # workflows.list ist gewachsen, oder ein erster Lauf brach ab) bliebe jeder
    # vorhandene ';true'-Workflow dann unveröffentlicht, auch fehler-melden,
    # während das Protokoll "übersprungen" meldet.
    #
    # Ein bereits aktiver Workflow wird NICHT angefasst: Hat der Betrieb einen
    # Mail-Workflow bewusst wieder abgeschaltet, ist das seine Entscheidung und
    # kein Zustand, den ein Setup-Lauf zurückdrehen darf.
    if [ "$active" = "true" ] && ! grep -qx "$wf_id" <<<"$active_ids"; then
      activate_ids+=("$wf_id")
      log "  ... steht auf ';true', ist aber nicht veröffentlicht - wird nachgeholt."
    fi
    continue
  fi

  # Statt `docker cp` (dessen "container:pfad"-Zielsyntax sich unter Git
  # Bash/Windows nicht sauber escapen ließ, getestet und verworfen): Datei per
  # stdin-Redirection in den Container schreiben. $file wird von Bash selbst
  # aufgelöst (kein Windows-Argv-Problem), der Container-Pfad im
  # `sh -c`-String ist ein reiner Container-Pfad → MSYS_NO_PATHCONV schützt
  # ihn vor Windows-Pfadkonvertierung.
  MSYS_NO_PATHCONV=1 docker exec -i -u node "$N8N_CONTAINER" sh -c 'cat > /tmp/setup-import.json' <"$file"
  MSYS_NO_PATHCONV=1 docker exec -u node "$N8N_CONTAINER" n8n import:workflow --input=/tmp/setup-import.json >/dev/null
  ok "importiert: $path (id=$wf_id)"
  imported=$((imported + 1))

  [ "$active" = "true" ] && activate_ids+=("$wf_id")
done <"$MANIFEST"

# ── Seeder für die Instanz-Einstellungen ────────────────────────────────────
# n8n/config-tabelle-schreiben.json füllt die Data Table 'pw_config', aus der
# ALLE Workflows ihre Adressen und URLs holen. Er steht bewusst NICHT im
# Manifest: er ist Installationswerkzeug, kein Workflow des Kunden, und wird
# weiter unten nach Gebrauch wieder unveröffentlicht.
#
# Wird, anders als die Workflows aus dem Manifest, IMMER importiert, auch
# ohne --force. Eine stehengebliebene alte Fassung würde sonst gegen ein
# geändertes Tabellenschema schreiben, und das fiele erst auf, wenn ein
# Workflow den fehlenden Schlüssel nicht findet.
CONFIG_FILE="$PROJECT_DIR/einstellungen/n8n/config.json"
SEEDER_FILE="$REPO_ROOT/n8n/config-tabelle-schreiben.json"
SEEDER_ID="pwConfigSchreib1"
seed_config=false

if [ -f "$CONFIG_FILE" ]; then
  jq empty "$CONFIG_FILE" 2>/dev/null \
    || die "Instanz-Einstellungen nicht lesbar oder kein gültiges JSON: $CONFIG_FILE"
  [ -f "$SEEDER_FILE" ] || die "Seeder-Workflow fehlt: $SEEDER_FILE"

  MSYS_NO_PATHCONV=1 docker exec -i -u node "$N8N_CONTAINER" sh -c 'cat > /tmp/setup-import.json' <"$SEEDER_FILE"
  MSYS_NO_PATHCONV=1 docker exec -u node "$N8N_CONTAINER" n8n import:workflow --input=/tmp/setup-import.json >/dev/null
  activate_ids+=("$SEEDER_ID")
  seed_config=true
  imported=$((imported + 1))
  ok "importiert: n8n/config-tabelle-schreiben.json (id=$SEEDER_ID)"
else
  warn "einstellungen/n8n/config.json nicht vorhanden - Instanz-Einstellungen werden NICHT gesetzt."
  warn "  Vorlage: cp config-template/einstellungen/n8n/config.json.example $CONFIG_FILE"
  warn "  Ohne die Data Table 'pw_config' brechen alle Workflows im Konfigurations-Node ab."
fi

if [ "$imported" -eq 0 ]; then
  [ "$skipped" -gt 0 ] && ok "n8n: alle $skipped Workflow(s) existierten bereits - nichts zu tun (--force zum Überschreiben)."
  [ "$skipped" -eq 0 ] && warn "Manifest enthält keine Workflows - nichts zu tun."
  exit 0
fi

# ${arr[@]+"${arr[@]}"} statt "${arr[@]}": In Bash 3.2 (der Version, die macOS
# bis heute als /bin/bash ausliefert) bricht die Expansion eines LEEREN Arrays
# unter `set -u` mit "unbound variable" ab, obwohl das Array oben deklariert ist
# (ab Bash 4.4 behoben, deshalb fällt es auf Linux nicht auf). Das trifft
# jede workflows.list, in der kein einziger Eintrag auf ';true' steht, also auch
# workflows.list.example und damit den normalen Kundeninstallationsweg auf einem
# Mac. `${#activate_ids[@]}` weiter unten ist davon nicht betroffen.
for wf_id in ${activate_ids[@]+"${activate_ids[@]}"}; do
  docker exec -u node "$N8N_CONTAINER" n8n publish:workflow --id="$wf_id" >/dev/null
  ok "aktiviert + veröffentlicht: id=$wf_id"
done

log "Starte n8n-Container neu, damit die Instanz die Änderungen übernimmt …"
docker restart "$N8N_CONTAINER" >/dev/null
wait_for_url "$N8N_URL/healthz" 45 2 \
  || die "n8n nach Restart nicht erreichbar ($N8N_URL/healthz)"

# ── Instanz-Einstellungen in die Data Table schreiben ───────────────────────
# Der Seeder-Workflow ist jetzt veröffentlicht und sein Webhook erreichbar.
# config.json geht als Body rein; _kommentar-Einträge fliegen vorher raus
# (gleiche Konvention wie bei credentials.json, nur dass es hier ein
# Array-Element ist statt eines Feldes).
if [ "$seed_config" = "true" ]; then
  # ACHTUNG: /healthz antwortet 'ok', BEVOR die Webhooks registriert sind;
  # der erste Aufruf läuft dann mehrere Sekunden lang in einen 404. Deshalb hier eine eigene Warteschleife auf den Webhook selbst
  # statt sich auf das bereits erfolgte healthz zu verlassen.
  config_body="$(jq -c '[.[] | select(has("key"))]' "$CONFIG_FILE")"
  anzahl="$(jq 'length' <<<"$config_body")"
  [ "$anzahl" -gt 0 ] || die "$CONFIG_FILE enthält keinen einzigen Eintrag mit 'key'."

  antwort=""
  for _ in $(seq 1 20); do
    # --data-binary @- über stdin, nicht als Argument: sonst zerschießt Git
    # Bash die Umlaute in den Hinweistexten (siehe lib/common.sh:papi).
    if antwort="$(printf '%s' "$config_body" | curl -sf -X POST \
        -H 'Content-Type: application/json' --data-binary @- \
        "$N8N_URL/webhook/pw-config-schreiben" 2>/dev/null)"; then
      break
    fi
    antwort=""
    sleep 2
  done

  [ -n "$antwort" ] \
    || die "Instanz-Einstellungen konnten nicht geschrieben werden - Webhook $N8N_URL/webhook/pw-config-schreiben antwortet nicht."

  ok "Data Table 'pw_config': $(jq -r '.geschrieben' <<<"$antwort") Schlüssel geschrieben."
  leer="$(jq -r '.noch_leer | join(", ")' <<<"$antwort")"
  [ -n "$leer" ] && warn "Noch ohne Wert: $leer - in der n8n-Oberfläche unter Data Tables → pw_config nachtragen."

  # Seeder wieder vom Netz nehmen: ein dauerhaft offener Webhook, der die
  # Betriebsadressen umschreiben kann, hat auf einer Kundeninstallation
  # nichts verloren. Der zweite Restart ist nötig, weil die laufende
  # Instanz DB-Änderungen der CLI erst danach sieht; dieselbe Stolperfalle
  # wie beim Import weiter oben.
  MSYS_NO_PATHCONV=1 docker exec -u node "$N8N_CONTAINER" \
    n8n unpublish:workflow --id="$SEEDER_ID" >/dev/null
  docker restart "$N8N_CONTAINER" >/dev/null
  wait_for_url "$N8N_URL/healthz" 45 2 \
    || die "n8n nach dem zweiten Restart nicht erreichbar ($N8N_URL/healthz)"
  ok "Seeder 'config-tabelle-schreiben' wieder unveröffentlicht."
fi

ok "n8n: $imported Workflow(s) importiert, ${#activate_ids[@]} aktiviert+veröffentlicht, $skipped übersprungen."
