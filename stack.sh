#!/usr/bin/env bash
# docker compose mit den Dateien einer Installation (siehe
# setup/lib/installation.sh). Intern für die Skripte unter setup/; der
# Einstieg für Anwender ist ./paper-werk.
#
#   ./stack.sh                      zeigt alle Installationen und was läuft
#   ./stack.sh up -d                startet die Installation in config/
#   ./stack.sh kunde up -d --build    eine benannte unter config-repos/
#   ./stack.sh kunde logs -f paperless
#
# Ist das erste Argument der Name einer Installation, gilt diese, sonst
# config/. Alle weiteren Argumente gehen unverändert an `docker compose`.
#
# WARUM ES DIESES SKRIPT GIBT
#
# Eine Installation besteht aus der Vorlage (compose/docker-compose.yml),
# je nach Wunsch dem Zusatzstück für HTTPS und den eigenen Ergänzungen des
# Betreibers. Der Aufruf dafür ist fünf Zeilen lang, und jeder tippt ihn
# anders. Wer ihn sich abkürzen will, kopiert die Vorlage in seinen
# Projektordner, und diese Kopie wird nie wieder nachgezogen.
# Deshalb: ein Befehl, und die Vorlage bleibt an EINER Stelle.
#
# Was eine Installation mitbringt, steht in ihrer instanz.conf.
#
# Alle -f-Pfade werden absolut übergeben: Compose löst sie gegen das
# AUFRUFVERZEICHNIS auf, nicht gegen --project-directory. Relative Pfade
# hingen damit daran, von wo aus jemand das Skript startet.
#
# Dieses Skript liegt bewusst NICHT in jedem Projektordner: Es wäre wieder
# eine Kopie. Es liegt einmal hier und kennt die Projekte am Namen.

set -euo pipefail
cd "$(dirname "$0")"
WURZEL="$(pwd)"

rot=$'\033[1;31m'; gruen=$'\033[1;32m'; blau=$'\033[1;34m'; aus=$'\033[0m'
meld() { printf '%s[stack]%s %s\n' "$blau" "$aus" "$*" >&2; }
ende() { printf '%s[Fehler]%s %s\n' "$rot" "$aus" "$*" >&2; exit 1; }

# Docker unter Windows will Windows-Pfade. In der Git Bash liefert `pwd -W`
# C:/..., unter Linux und macOS gibt es die Option nicht; dort ist der
# gewöhnliche Pfad der richtige.
als_hostpfad() {
  ( cd "$1" && { pwd -W 2>/dev/null || pwd; } )
}

laeuft() { [ -n "$(docker ps -q --filter "label=com.docker.compose.project=$1" 2>/dev/null)" ]; }

# Wo eine Installation liegt: config/ oder config-repos/paper-werk-config-<name>.
# shellcheck source=setup/lib/installation.sh
source setup/lib/installation.sh

zeige() {
  local d="$1" o="$2" art="Vorlage"
  [ -f "$o/instanz.conf" ] || art="eigene Kopie (alter Aufbau)"
  [ -f "$o/.env" ] || art="$art, ohne .env"
  art="$art, $o"
  if laeuft "$(compose_projekt "$o")"; then printf '  %s●%s %-12s %s (läuft)\n' "$gruen" "$aus" "$d" "$art"
  else                                       printf '  ○ %-12s %s\n' "$d" "$art"; fi
}

liste() {
  local d o
  o="$(installationsordner)" && zeige "(config)" "$o"
  for d in $(installationen); do
    o="$(installationsordner "$d")" || continue
    zeige "$d" "$o"
  done
}

[ $# -eq 0 ] && { liste; exit 0; }

name=""
if ist_installation "$1"; then
  name="$1"; shift
fi
ordner="$(installationsordner "$name")" || {
  if [ -n "$name" ]; then printf 'Keine Installation: %s\n\n' "$name" >&2
  else printf 'Weder config/ noch eine Installation "%s".\n\n' "$1" >&2; fi
  liste >&2; exit 1; }

# --- Welche Dateien gelten? --------------------------------------------------

dateien=()
projektname="$(compose_projekt "$ordner")"

if [ -f "$ordner/instanz.conf" ]; then
  # Voreinstellungen; instanz.conf überschreibt, was sie nennt.
  PROJEKT="$projektname"; HTTPS="nein"; PROFILE=""; ZUSATZ=""; APP_BAUEN="nein"
  # shellcheck disable=SC1090
  source "$ordner/instanz.conf"
  projektname="$PROJEKT"

  dateien+=(-f "$WURZEL/compose/docker-compose.yml")
  [ "$HTTPS" = "ja" ] && dateien+=(-f "$WURZEL/compose/compose.https.yml")
  # Vor ZUSATZ: Eine Installation kann dort den Namen des gebauten Images
  # ändern (lasttest baut paper-werk-app-lasttest:latest).
  [ "$APP_BAUEN" = "ja" ] && dateien+=(-f "$WURZEL/compose/compose.build.yml")
  # Scanner-Ablage als Ordner auf dem Host, wenn .env einen nennt.
  grep -qsE '^[[:space:]]*PAPER_WERK_CONSUME_ORDNER=.+' "$ordner/.env" \
    && dateien+=(-f "$WURZEL/compose/compose.consume-ordner.yml")

  for z in $ZUSATZ; do
    [ -f "$ordner/$z" ] || ende "In instanz.conf steht ZUSATZ=\"$z\", aber die Datei fehlt: $ordner/$z"
    dateien+=(-f "$WURZEL/$ordner/$z")
  done

  # Eigene Ergänzungen des Betreibers. compose.override.yml kommt immer dazu,
  # wenn sie da ist. Das ist der vorgesehene Ort für Änderungen vor Ort, und
  # er braucht keinen Eintrag in instanz.conf, damit ihn auch findet, wer
  # diese Datei nie gelesen hat.
  #
  # Sie kommt ZULETZT: Wer vor Ort etwas ändern muss, soll das letzte Wort
  # haben, auch gegenüber allem, was in ZUSATZ steht.
  [ -f "$ordner/compose.override.yml" ] && dateien+=(-f "$WURZEL/$ordner/compose.override.yml")

  for p in $PROFILE; do dateien+=(--profile "$p"); done

  # Der Ordner mit Caddyfile und Einstiegsseite. Compose löst den relativen
  # Pfad gegen --project-directory auf, also gegen den Projektordner; dort
  # liegt der Ordner aber nur, wenn die Installation eine eigene Seite hat.
  # Sonst gilt der der Vorlage. Wer die Variable selbst in .env
  # setzt, behält das letzte Wort.
  if ! grep -qs '^[[:space:]]*PAPER_WERK_CADDY_DIR=' "$ordner/.env"; then
    if [ -d "$ordner/caddy" ]; then
      export PAPER_WERK_CADDY_DIR="$(als_hostpfad "$ordner/caddy")"
    else
      export PAPER_WERK_CADDY_DIR="$(als_hostpfad "$WURZEL/compose/caddy")"
    fi
  fi

  # Der Build-Kontext von paper-werk-app (APP_BAUEN=ja). Compose löst den
  # relativen Vorgabewert gegen das PROJEKTVERZEICHNIS auf, nicht gegen die
  # Vorlage, und fände das Repo dort nicht. Deshalb hier: das Repo neben
  # diesem, so wie Kundeninstallation.md es anlegt.
  if ! grep -qs '^[[:space:]]*PAPER_WERK_APP_CONTEXT=' "$ordner/.env"; then
    if [ -f "$WURZEL/../paper-werk-app/Dockerfile" ]; then
      PAPER_WERK_APP_CONTEXT="$(als_hostpfad "$WURZEL/../paper-werk-app")"
      export PAPER_WERK_APP_CONTEXT
    fi
  fi
else
  # Alter Aufbau: eigene docker-compose.yml im Projektordner. Läuft weiter,
  # wird aber nicht mehr mitgezogen.
  [ -f "$ordner/docker-compose.yml" ] || ende "$ordner hat weder instanz.conf noch docker-compose.yml"
  dateien+=(-f "$WURZEL/$ordner/docker-compose.yml")
fi

befehl=(docker compose "${dateien[@]}" --project-directory "$ordner" -p "$projektname")

# --- Was ist zu tun? ---------------------------------------------------------

[ $# -eq 0 ] && ende "Was soll docker compose tun? up -d, down, config, logs ..."

if [ ! -f "$ordner/.env" ]; then
    ende "$ordner/.env fehlt. Anlegen aus den Vorlagen:
    cd $ordner
    for v in $WURZEL/config-template/.env*.example; do cp -n \"\$v\" \"\$(basename \"\${v%.example}\")\"; done
    und danach durchsehen - ohne ausgefüllte Werte startet nichts."
fi

meld "$(anzeigename "$name") (-p $projektname)"
exec "${befehl[@]}" "$@"
