#!/usr/bin/env bash
# Gemeinsame Helfer für die Setup-Skripte. Wird per `source` eingebunden,
# nicht direkt ausgeführt.

set -euo pipefail

# Hinweis Windows/Git Bash: MSYS würde Argumente wie /tmp/... oder
# /source/... in Windows-Pfade umschreiben, bevor sie bei docker exec
# ankommen. NICHT global abschalten (export MSYS_NO_PATHCONV=1); das
# würde auch Host-Pfade für native Windows-Tools wie jq unbrauchbar machen
# Stattdessen wird
# MSYS_NO_PATHCONV nur pro Docker-Aufruf gesetzt, die einen reinen
# Container-Pfad übergeben (siehe kopia/apply.sh:kexec(),
# n8n/apply.sh).

# Zwei Ebenen ("../..") zeigten aus dem Repo heraus und ließen den
# n8n-Workflow-Import mit "Workflow-Datei fehlt" scheitern.
# und ließ den n8n-Workflow-Import mit "Workflow-Datei fehlt" scheitern.
SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SETUP_DIR/.." && pwd)"

log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ ok ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fehler]\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "Benötigtes Programm fehlt: $c"
  done
}

load_conf() {
  [ -n "${PROJECT_DIR:-}" ] || die "PROJECT_DIR nicht gesetzt – setup.sh mit --project <projektordner> aufrufen."
  [ -d "$PROJECT_DIR" ] || die "Projektordner nicht gefunden: $PROJECT_DIR"
  local conf="$PROJECT_DIR/einstellungen/setup.conf"
  # Alter Aufbau: Die Werte lagen unter <projekt>/setup/.
  # Seit dem Umbau heißt der Ordner einstellungen/, damit es nicht zweimal
  # „setup" gibt. Ein Projekt im alten Aufbau wird nicht still weiter
  # unterstützt, sondern klar abgewiesen, weil das Skript sonst nur
  # „setup.conf fehlt“ meldete und man an der falschen Stelle suchte.
  if [ ! -f "$conf" ] && [ -f "$PROJECT_DIR/setup/setup.conf" ]; then
    die "Dieses Projekt hat noch den alten Aufbau (setup/ statt einstellungen/). Ordner umbenennen: mv \"$PROJECT_DIR/setup\" \"$PROJECT_DIR/einstellungen\" – Hintergrund in $PROJECT_DIR/ALTER-AUFBAU.md, falls vorhanden."
  fi
  [ -f "$conf" ] || die "setup.conf fehlt – bitte 'cp config-template/einstellungen/setup.conf.example $PROJECT_DIR/einstellungen/setup.conf' und ausfüllen."
  # shellcheck source=/dev/null
  source "$conf"
}

# Paperless-REST-API-Aufruf mit Token-Auth.
#   papi GET  /api/tags/
#   papi POST /api/tags/ '{"name":"NEU"}'
#
# ── Der Weg: durch den Container, nicht über den Host ────────────────────────
#
# Ist PAPERLESS_CONTAINER gesetzt, läuft der Aufruf per docker exec IM
# Paperless-Container gegen http://localhost:8000, also direkt an Paperless,
# ohne Caddy, ohne Zertifikat, ohne veröffentlichten Port. Im
# HTTPS-Betrieb (compose.https.yml) ist das der einzige Weg, der immer geht:
# Dort veröffentlicht Paperless keinen Port mehr, und PAPERLESS_URL
# (http://localhost:8005) führt ins Leere bzw. auf Caddy, dessen Zertifikat
# curl im Modus "intern" nicht kennt. Im http-Betrieb ist es gleichwertig.
#
# Fehlt PAPERLESS_CONTAINER (ältere setup.conf),
# bleibt es beim alten Weg über PAPERLESS_URL, mit einer Warnung. Eine
# laufende Installation soll an diesem Umbau nicht brechen.
papi() {
  local method="$1" path="$2" body="${3:-}"
  local args=(-sf -X "$method"
    -H "Authorization: Token $PAPERLESS_TOKEN"
    -H "Content-Type: application/json")
  if [ -n "${PAPERLESS_CONTAINER:-}" ]; then
    # Body über stdin (-i), aus demselben Grund wie unten: Umlaute überleben
    # keine Kommandozeile unter Git Bash. MSYS_NO_PATHCONV, damit Git Bash
    # nichts an den Argumenten für docker umschreibt.
    if [ -n "$body" ]; then
      printf '%s' "$body" | MSYS_NO_PATHCONV=1 docker exec -i "$PAPERLESS_CONTAINER" \
        curl "${args[@]}" --data-binary @- "http://localhost:8000$path"
    else
      MSYS_NO_PATHCONV=1 docker exec "$PAPERLESS_CONTAINER" \
        curl "${args[@]}" "http://localhost:8000$path"
    fi
    return
  fi
  _papi_warnung_einmal
  if [ -n "$body" ]; then
    # Body über stdin (--data-binary @-) statt als Kommandozeilen-Argument:
    # Git Bash auf Windows würde Nicht-ASCII-Zeichen (Umlaute) in
    # Argumenten für native Windows-Programme wie curl.exe über die
    # System-ANSI-Codepage umkodieren und damit UTF-8 zerstören (z. B. "ä"
    # von 2 Bytes auf 1 falsches Byte). Pipes/stdin sind davon nicht
    # betroffen. Auf Linux/macOS wirkungslos, aber unschädlich.
    printf '%s' "$body" | curl "${args[@]}" --data-binary @- "$PAPERLESS_URL$path"
  else
    curl "${args[@]}" "$PAPERLESS_URL$path"
  fi
}

_papi_warnung_gegeben=""
_papi_warnung_einmal() {
  [ -n "$_papi_warnung_gegeben" ] && return 0
  _papi_warnung_gegeben=1
  warn "PAPERLESS_CONTAINER fehlt in setup.conf - Paperless wird über $PAPERLESS_URL angesprochen."
  warn "  Im HTTPS-Betrieb geht das nicht. Nachtragen, z. B. PAPERLESS_CONTAINER=\"<projekt>-paperless-1\"."
}

# Wartet, bis Paperless antwortet, auf demselben Weg, den papi nimmt.
paperless_bereit() {
  local versuche="${1:-30}" pause="${2:-2}" i
  if [ -z "${PAPERLESS_CONTAINER:-}" ]; then
    _papi_warnung_einmal
    wait_for_url "$PAPERLESS_URL/api/" "$versuche" "$pause"
    return
  fi
  for ((i = 1; i <= versuche; i++)); do
    if MSYS_NO_PATHCONV=1 docker exec "$PAPERLESS_CONTAINER" \
         curl -sf -o /dev/null http://localhost:8000/api/ 2>/dev/null; then
      return 0
    fi
    sleep "$pause"
  done
  return 1
}

# Wartet auf das Lebenszeichen der App IM App-Container, nicht über den Host.
#
# Warum nicht APP_URL: Im HTTPS-Betrieb veröffentlicht die App keinen Port,
# und Caddy davor spricht nur TLS. Warum Python und nicht curl: Das Image der
# App hat kein curl, Python hat es ohnehin. Und warum paper-werk-app statt
# localhost: Im HTTPS-Betrieb lässt die App "localhost" nicht mehr als
# Hostnamen zu (DJANGO_ALLOWED_HOSTS aus compose.https.yml); ihr Dienstname
# steht in beiden Betriebsarten darin, weil n8n sie genau so anspricht.
app_bereit() {
  local versuche="${1:-60}" pause="${2:-2}" i
  for ((i = 1; i <= versuche; i++)); do
    if MSYS_NO_PATHCONV=1 docker exec "$APP_CONTAINER" python -c \
         "import urllib.request; urllib.request.urlopen('http://paper-werk-app:8000/api/v1/status/', timeout=5)" \
         >/dev/null 2>&1; then
      return 0
    fi
    sleep "$pause"
  done
  return 1
}

# Wartet, bis eine URL HTTP 2xx liefert (Argumente: URL, Versuche, Pause in s).
wait_for_url() {
  local url="$1" tries="${2:-30}" pause="${3:-2}" i
  for ((i = 1; i <= tries; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then return 0; fi
    sleep "$pause"
  done
  return 1
}
