#!/usr/bin/env bash
# Zustandsbericht einer Installation, der Bericht, den man im Störungsfall
# schickt.
#
#   ./setup/doktor.sh                 die Installation in config/
#   ./setup/doktor.sh kunde             eine benannte unter config-repos/
#   ./setup/doktor.sh kunde > bericht.txt
#
# Er beantwortet vier Fragen, die sonst jedes Mal einzeln gestellt werden:
#
#   1. Welcher Stand läuft?
#   2. Wurde an dem geändert, was das Repo ausliefert? (compose/, setup/, n8n/ …)
#   3. Was gehört dem Betreiber, und ist es vollständig?
#   4. Laufen die Container, und ist das Zertifikat noch gültig?
#
# Frage 2 ist der eigentliche Grund. Eine Installation, die ein fremder
# Systembetreuer aufbaut, kann lokal geändert sein; ein `git status` auf
# die ausgelieferten Ordner macht das sichtbar, bevor es beim nächsten
# `git pull` als Konflikt auffällt. Wer etwas ändern muss, legt dafür eine
# compose.override.yml in den Projektordner; die meldet dieser Bericht als
# gewollt, nicht als Abweichung.
#
# Der Bericht ist absichtlich nur Text: Er wird gelesen, kopiert und
# weitergeschickt. Er ändert nichts, startet nichts und braucht kein Netz -
# ohne Netz bleibt allein der Vergleich mit dem Stand im Netz aus.
#
# Versionsstände (Tags) gibt es noch nicht; bis dahin steht hier der Commit.

set -euo pipefail
cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

AUSGELIEFERT=(compose config-template setup n8n starterpakete demodaten)

rot=$'\033[1;31m'; gelb=$'\033[1;33m'; gruen=$'\033[1;32m'; leise=$'\033[2m'; aus=$'\033[0m'
zeile()  { printf '%-12s %s\n' "$1" "$2"; }
achtung() { printf '%-12s %s⚠ %s%s\n' "$1" "$gelb" "$2" "$aus"; }
fehler()  { printf '%-12s %s✖ %s%s\n' "$1" "$rot" "$2" "$aus"; }
gut()     { printf '%-12s %s%s%s\n' "$1" "$gruen" "$2" "$aus"; }

# shellcheck source=lib/installation.sh
source setup/lib/installation.sh
name="${1:-}"
if [ -n "$name" ] && ! ist_installation "$name"; then
  echo "Keine Installation: $name" >&2; echo; ./stack.sh; exit 1
fi
ordner="$(installationsordner "$name")" || {
  echo "Aufruf: ./setup/doktor.sh [<installation>]; ohne Namen gilt config/, und das fehlt."; echo; ./stack.sh; exit 1; }

printf '\npaper-werk – Zustand der Installation "%s"%s%s%s\n\n' \
       "$(anzeigename "$name")" "$leise" "          $(date '+%Y-%m-%d %H:%M')" "$aus"

# ── 1. Welcher Stand? ────────────────────────────────────────────────────────

if git -C "$WURZEL" rev-parse --git-dir >/dev/null 2>&1; then
  zeile "Stand" "$(git -C "$WURZEL" log -1 --format='%h  "%s"  (%ad)' --date=short)"
  zweig="$(git -C "$WURZEL" rev-parse --abbrev-ref HEAD)"
  zeile "" "Zweig $zweig"
  if git -C "$WURZEL" rev-parse "@{upstream}" >/dev/null 2>&1; then
    hinter="$(git -C "$WURZEL" rev-list --count HEAD..@{upstream} 2>/dev/null || echo '?')"
    vor="$(git -C "$WURZEL" rev-list --count @{upstream}..HEAD 2>/dev/null || echo '?')"
    [ "$hinter" != "0" ] && achtung "" "$hinter Commits hinter $(git -C "$WURZEL" rev-parse --abbrev-ref '@{upstream}') – Stand von vor dem letzten Abruf"
    [ "$vor" != "0" ]    && achtung "" "$vor eigene Commits, die nirgends sonst liegen"
  else
    zeile "" "kein Gegenstück im Netz eingetragen"
  fi
else
  achtung "Stand" "kein Git-Arbeitsverzeichnis – Stand nicht feststellbar"
fi
echo

# ── 2. Wurde am Ausgelieferten geändert? ─────────────────────────────────────

geaendert=""
for d in "${AUSGELIEFERT[@]}"; do
  [ -d "$WURZEL/$d" ] || continue
  if git -C "$WURZEL" rev-parse --git-dir >/dev/null 2>&1; then
    aenderungen="$(git -C "$WURZEL" status --porcelain -- "$d" 2>/dev/null || true)"
    if [ -n "$aenderungen" ]; then
      anzahl="$(printf '%s\n' "$aenderungen" | wc -l | tr -d ' ')"
      geaendert="$geaendert$d "
      achtung "Ausgeliefert" "$d/ – $anzahl Datei(en) geändert:"
      printf '%s\n' "$aenderungen" | sed 's/^/             /'
    fi
  fi
done
if [ -z "$geaendert" ]; then
  gut "Ausgeliefert" "unverändert (${AUSGELIEFERT[*]})"
else
true   # der Umfang steht gleich darunter, Zeile für Zeile
  for d in $geaendert; do
    git -C "$WURZEL" --no-pager diff --stat -- "$d" | sed 's/^/             /'
  done
  printf '%-12s %s
' "" "(?? heißt: neue Datei, M heißt: an einer von uns geändert)"
  printf '%-12s %s\n' "" "Änderungen gehören in $ordner/compose.override.yml,"
  printf '%-12s %s\n' "" "nicht in die ausgelieferten Dateien - sonst kollidiert der nächste Abruf."
fi
echo

# ── 3. Was gehört dem Betreiber? ─────────────────────────────────────────────

if [ -f "$ordner/instanz.conf" ]; then
  PROJEKT="$(compose_projekt "$ordner")"; HTTPS="nein"; PROFILE=""; ZUSATZ=""
  # shellcheck disable=SC1090
  source "$ordner/instanz.conf"
  zeile "Eigenes" "instanz.conf: Projekt $PROJEKT, HTTPS $HTTPS${PROFILE:+, Profile $PROFILE}${ZUSATZ:+, Zusatz $ZUSATZ}"
else
  PROJEKT="$(compose_projekt "$ordner")"; HTTPS="nein"
  achtung "Eigenes" "keine instanz.conf – alter Aufbau mit eigener docker-compose.yml"
fi

if [ -f "$ordner/compose.override.yml" ]; then
  zeile "" "compose.override.yml vorhanden ($(grep -cE '^[[:space:]]{2}[a-z-]+:' "$ordner/compose.override.yml" || echo '?') Dienste berührt)"
fi

[ -f "$ordner/.env" ] || fehler "" ".env fehlt - ohne sie startet nichts"

# Den Vergleich mit den Vorlagen macht env-abgleich.sh; es unterscheidet
# schon zwischen Pflichtschlüsseln und auskommentierten Angeboten. Eine
# zweite Fassung dieser Logik hier wäre die, die als Erste veraltet.
printf '%-12s %s
' "" "Abgleich der .env-Dateien mit den Vorlagen:"
./setup/env-abgleich.sh "$ordner" 2>&1 | sed 's/^/             /' || true
echo

# ── 4. Läuft es? ─────────────────────────────────────────────────────────────

if ! command -v docker >/dev/null 2>&1; then
  fehler "Container" "docker nicht gefunden"
else
  laufend="$(docker ps --filter "label=com.docker.compose.project=$PROJEKT" --format '{{.Names}}\t{{.Status}}' 2>/dev/null || true)"
  alle="$(docker ps -a --filter "label=com.docker.compose.project=$PROJEKT" --format '{{.Names}}\t{{.Status}}' 2>/dev/null || true)"
  if [ -z "$alle" ]; then
    achtung "Container" "keine – diese Installation ist nie gestartet oder heißt anders (-p $PROJEKT)"
  else
    zeile "Container" "$(printf '%s\n' "$laufend" | grep -c . ) von $(printf '%s\n' "$alle" | grep -c . ) laufen"
    printf '%s\n' "$alle" | grep -v "Up " | grep . | sed "s/^/             ${gelb}⚠${aus} /" || true
  fi
fi

if [ "$HTTPS" = "ja" ]; then
  host="$(grep -E '^PAPER_WERK_HOSTNAME=' "$ordner/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
  modus="$(grep -E '^PAPER_WERK_TLS_MODE=' "$ordner/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
  zeile "HTTPS" "Name ${host:-?}, Zertifikat ${modus:-intern}"
  if [ -n "$host" ] && command -v openssl >/dev/null 2>&1; then
    bis="$(echo | openssl s_client -connect "${host}:443" -servername "$host" 2>/dev/null \
           | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || true)"
    if [ -n "$bis" ]; then
      tage=$(( ( $(date -d "$bis" +%s 2>/dev/null || echo 0) - $(date +%s) ) / 86400 ))
      if [ "${modus:-intern}" = intern ]; then
        # Caddy als eigene Zertifizierungsstelle stellt Blätter mit ZWÖLF
        # STUNDEN Laufzeit aus und erneuert sie selbst. Eine Restlaufzeit
        # von 0 Tagen ist hier der Normalfall und keine Meldung wert. Zu
        # beobachten ist stattdessen das Stammzertifikat (zehn Jahre), das
        # auf den Arbeitsplätzen liegt.
        if [ "$tage" -lt 0 ]; then achtung "" "Zertifikat abgelaufen und nicht erneuert - läuft Caddy?"
        else                       zeile   "" "Zertifikat von Caddy selbst, erneuert sich automatisch (gültig bis $bis)"; fi
      elif [ "$tage" -lt 0 ];  then fehler  "" "Zertifikat ABGELAUFEN seit $(( -tage )) Tagen"
      elif [ "$tage" -lt 30 ]; then achtung "" "Zertifikat läuft in $tage Tagen ab - Ersatz bei der IT anfordern"
      else                          zeile   "" "Zertifikat gültig bis $bis ($tage Tage)"; fi
    else
      achtung "" "kein Zertifikat abrufbar – läuft Caddy, und zeigt der Name hierher?"
    fi
  fi
fi

# Die nächtliche Sicherung ist Kopias eigener Zeitplan; fällt er aus, meldet
# Kopia das nicht von sich aus. Älter als 26 Stunden ist verdächtig.
kopia="$PROJEKT-kopia-1"
if command -v docker >/dev/null 2>&1; then
  if [ "$(docker inspect -f '{{.State.Running}}' "$kopia" 2>/dev/null)" != true ]; then
    achtung "Sicherung" "Kopia läuft nicht ($kopia)"
  elif ! liste="$(MSYS_NO_PATHCONV=1 docker exec "$kopia" kopia snapshot list /source/paper-werk --json 2>&1)"; then
    case "$liste" in
      *"not connected"*) achtung "Sicherung" "Kopia ist mit keinem Repository verbunden; es wird nichts gesichert" ;;
      *)                 achtung "Sicherung" "Kopia: $(printf '%s' "$liste" | head -c 120)" ;;
    esac
  else
    letzte="$(printf '%s' "$liste" | jq -r 'map(.startTime) | max // empty' 2>/dev/null || true)"
    if [ -z "$letzte" ]; then
      achtung "Sicherung" "noch kein Snapshot von /source/paper-werk"
    else
      stunden=$(( ( $(date +%s) - $(date -d "$letzte" +%s 2>/dev/null || echo 0) ) / 3600 ))
      text="letzter Snapshot $(date -d "$letzte" '+%Y-%m-%d %H:%M' 2>/dev/null) (${stunden} h)"
      if [ "$stunden" -gt 26 ]; then achtung "Sicherung" "$text; läuft der Zeitplan in Kopia?"
      else                          zeile   "Sicherung" "$text"; fi
    fi
  fi
fi
echo
