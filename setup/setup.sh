#!/usr/bin/env bash
# Orchestrator für die skriptgesteuerte Erstinstallation.
# Läuft auf dem Docker-Host, nachdem der Compose-Stack des Projekts
# (config/ oder config-repos/paper-werk-config-<name>) oben ist.
#
# Aufruf:
#   ./setup.sh --project ../config              # alle Module
#   ./setup.sh --project ../config app          # nur paper-werk-app
#   ./setup.sh --project ../config paperless    # nur Paperless-Starterpaket
#   ./setup.sh --project ../config n8n kopia    # Auswahl
#   ./setup.sh --project ../config sso          # Gruppe und Freigaben
#                                                           # für die gemeinsame
#                                                           # Anmeldung, NICHT im
#                                                           # Standardlauf
#   ./setup.sh --project ../config n8n --force  # vorhandene n8n-Workflows
#                                                           # überschreiben statt
#                                                           # überspringen (siehe n8n/apply.sh)

set -euo pipefail
cd "$(dirname "$0")"
source lib/common.sh

modules=()
force=false
project=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) project="${2:-}"; shift 2 ;;
    --force) force=true; shift ;;
    *) modules+=("$1"); shift ;;
  esac
done

[ -n "$project" ] || die "Aufruf: ./setup.sh --project <projektordner> [modul ...] [--force]"
[ -d "$project" ] || die "Projektordner nicht gefunden: $project"
export PROJECT_DIR
PROJECT_DIR="$(cd "$project" && pwd)"

[ ${#modules[@]} -eq 0 ] && modules=(app paperless n8n kopia)
export SETUP_FORCE="$force"

for m in "${modules[@]}"; do
  case "$m" in
    app|paperless|n8n|kopia|sso)
      log "── Modul: $m (Projekt: $PROJECT_DIR) ──────────────────────────────"
      bash "$m/apply.sh"
      ;;
    *) die "Unbekanntes Modul: $m (erlaubt: app, paperless, n8n, kopia, sso, --force)" ;;
  esac
done

ok "Setup abgeschlossen."
