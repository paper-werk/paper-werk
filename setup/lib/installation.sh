#!/usr/bin/env bash
# Wo eine Installation liegt. Per `source` eingebunden von stack.sh,
# setup/doktor.sh, setup/aktualisieren.sh und
# setup/kopia/sicherung.sh; alle Pfade relativ zur Wurzel von paper-werk.
#
# Zwei Orte:
#
#   config/                                   die Installation dieses Rechners,
#                                             angesprochen ohne Namen
#   config-repos/paper-werk-config-<name>     mehrere Installationen auf einem
#                                             Rechner (Entwicklung), mit Namen
#
# Ein Kunde hat genau eine Installation und damit nur config/. Ob config/ ein
# geklontes Config-Repo ist oder ein einfacher Ordner, spielt hier keine Rolle.
#
# Rückfall für ältere Installationen: projekte/paper-werk-config-<name>
# und projekte/<name>. Liegt ein Name an mehr als einem Ort, ist das ein
# Abbruch, sonst entschiede die Reihenfolge still, welche Konfiguration gilt.
#
# Gültig ist ein Ordner mit instanz.conf oder, alter Aufbau, docker-compose.yml.
# paper-werk-config-archiv hat keins von beiden und taucht deshalb nicht auf.

CONFIG_PRAEFIX="paper-werk-config-"

# installationsordner [<name>]: gibt den Ordner aus. Ohne Namen config/.
# Exit 1 = gibt es nicht, Exit 2 = an mehreren Orten.
installationsordner() {
  if [ -z "${1:-}" ]; then
    [ -d config ] || return 1
    printf 'config\n'
    return 0
  fi
  local k treffer=()
  for k in "config-repos/$CONFIG_PRAEFIX$1" "projekte/$CONFIG_PRAEFIX$1" "projekte/$1"; do
    [ -d "$k" ] && treffer+=("$k")
  done
  case ${#treffer[@]} in
    0) return 1 ;;
    1) printf '%s\n' "${treffer[0]}" ;;
    *) printf 'Installation "%s" liegt mehrfach vor: %s. Bis auf einen entfernen.\n' "$1" "${treffer[*]}" >&2
       return 2 ;;
  esac
}

_gueltig() { [ -f "$1/instanz.conf" ] || [ -f "$1/docker-compose.yml" ]; }

# installationen: Namen aller benannten Installationen, eine je Zeile,
# sortiert. config/ hat keinen Namen und steht nicht darin.
installationen() {
  local d n
  for d in config-repos/*/ projekte/*/; do
    [ -d "$d" ] || continue
    d="${d%/}"; n="${d#*/}"; n="${n#"$CONFIG_PRAEFIX"}"
    [ "$n" = "archiv" ] && continue
    _gueltig "$d" && printf '%s\n' "$n"
  done | sort -u
}

# ist_installation <wort>: 0, wenn <wort> eine benannte Installation ist.
# Damit unterscheiden die Skripte `./stack.sh dev up -d` von `./stack.sh up -d`.
ist_installation() {
  [ -n "${1:-}" ] && installationen | grep -qx -- "$1"
}

# anzeigename [<name>]: der Name für Meldungen; config/ heißt "config".
anzeigename() { printf '%s\n' "${1:-config}"; }

# compose_projekt <ordner>: Compose-Projektname (PROJEKT aus instanz.conf, sonst
# der Name der Installation, für config/ "paper-werk"). Nicht der Ordnername:
# kunde läuft etwa als paper-werk-kunde.
compose_projekt() {
  local ordner="$1" n
  n="$(basename "$ordner")"; n="${n#"$CONFIG_PRAEFIX"}"
  [ "$ordner" = "config" ] && n="paper-werk"
  if [ -f "$ordner/instanz.conf" ]; then
    ( PROJEKT="$n"; source "$ordner/instanz.conf" >/dev/null 2>&1; printf '%s\n' "$PROJEKT" )
  else
    printf '%s\n' "$n"
  fi
}
