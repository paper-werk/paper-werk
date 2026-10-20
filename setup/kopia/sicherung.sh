#!/usr/bin/env bash
# Zieht einen Kopia-Snapshot bei stehenden Datenbanken.
#
#   ./setup/kopia/sicherung.sh <installationsordner>
#
# Aufgerufen von setup/aktualisieren.sh vor jedem Update und von Hand vor
# riskanten Eingriffen. Stillstand auf einem Testsystem: 16 Sekunden
# (2 s stoppen, 8 s Snapshot, 6 s starten).
#
# Die nächtliche Sicherung macht Kopias eigener Zeitplan (Policy der Quelle
# /source/paper-werk, gesetzt von setup/kopia/apply.sh), bei laufenden
# Datenbanken. Ein Auslöser, sichtbar in der Kopia-Oberfläche,
# nichts abgeschaltet, das jemand wieder einschaltet, kein cron, der still
# ausfallen kann. Der Preis steht unten unter "Warum überhaupt gestoppt
# wird": Zwischen den beiden Datenbanken ist eine nächtliche Sicherung nur
# in der Regel konsistent. Nach einem Restore deshalb immer
# "manage.py pruefe_belegarchiv" in der App; es findet Belege, deren
# Dokument in Paperless fehlt. Ob die Sicherung läuft, prüft setup/doktor.sh
# (Alter des letzten Snapshots).
#
# ── Warum überhaupt gestoppt wird ────────────────────────────────────────────
#
# Ein Dateisystem-Snapshot einer LAUFENDEN Postgres-Instanz ist nicht
# konsistent, sondern nur "crash-consistent": Postgres repariert beim
# nächsten Start per WAL-Replay. Im Restore-Test meldeten beide Datenbanken
# "redo done", und die Daten stimmten; zugesagt ist das nicht.
#
# **Der eigentliche Grund ist ein anderer, und er betrifft nur diesen
# Stack:** Hier stehen ZWEI Datenbanken, die zueinander passen müssen. Ein
# festgeschriebener Beleg in `paper-werk-db` trägt die `paperless_id` seines
# Dokuments in `paperless-db`. Wird der Beleg genau zwischen den beiden
# Volume-Kopien festgeschrieben, zeigt der Verweis nach dem Restore ins
# Leere, und das merkt niemand, bis Wochen später jemand daraufklickt.
#
# Stehen beide Datenbanken, kann das nicht passieren. Die Konsistenz ist
# dann nicht wahrscheinlich, sondern zugesichert.
#
# ── Warum nicht pg_dump ──────────────────────────────────────────────────────
#
# Wäre der naheliegende Weg (und steht so in backblaze_kopia.md), löst aber
# genau das Problem oben NICHT: Zwei Dumps nacheinander sind jeder für sich
# konsistent, zueinander aber nicht. Dazu käme ein zweiter Restore-Weg, den
# niemand geübt hat, und ein Auslöser, der still ausfallen kann. Ein paar
# Sekunden Stillstand sind billiger als all das.
#
set -euo pipefail

HIER="$(cd "$(dirname "$0")" && pwd)"
WURZEL="$(cd "$HIER/../.." && pwd)"

log()  { printf '\033[1;34m[sicherung]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[achtung]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[fehler]\033[0m %s\n' "$*" >&2; exit 1; }

PROJEKT="${1:-}"
[ -n "$PROJEKT" ] || die "Aufruf: $0 <projektordner>"
[ -d "$PROJEKT" ] || die "Projektordner nicht gefunden: $PROJEKT"
PROJEKT="$(cd "$PROJEKT" && pwd)"
[ -f "$PROJEKT/einstellungen/setup.conf" ] || die "setup.conf fehlt in $PROJEKT/einstellungen/"

# shellcheck disable=SC1091
source "$PROJEKT/einstellungen/setup.conf"
: "${KOPIA_CONTAINER:?KOPIA_CONTAINER fehlt in setup.conf}"
: "${KOPIA_SOURCE_PATH:=/source/paper-werk}"

#: **Compose nur über stack.sh**, nie selbst zusammengesetzt.
#
# Ein eigener Aufruf mit `-p <ordnername>` zielt auf einen Stack, den es
# nicht gibt, sobald PROJEKT in instanz.conf vom Ordnernamen abweicht:
# `stop` hielte nichts an, der Snapshot liefe bei laufenden Datenbanken, und
# das Skript meldete trotzdem Erfolg.
# stack.sh kennt Projektname, HTTPS-Zusatz und compose.override.yml.
#
# Der Name für stack.sh folgt aus dem Ort (setup/lib/installation.sh):
# config/ ohne Namen, sonst config-repos/paper-werk-config-<name> bzw. bis zum
# Umzug projekte/paper-werk-config-<name> oder projekte/<name>.
NAME="$(basename "$PROJEKT")"
if [ "$PROJEKT" = "$WURZEL/config" ]; then
    COMPOSE=("$WURZEL/stack.sh")
else
    case "$PROJEKT" in
      "$WURZEL/config-repos/$NAME"|"$WURZEL/projekte/$NAME") ;;
      *) die "Installationsordner muss config/ sein oder unter config-repos/ liegen: $PROJEKT" ;;
    esac
    COMPOSE=("$WURZEL/stack.sh" "${NAME#paper-werk-config-}")
fi

#: Was für die Dauer des Snapshots stillsteht.
#
# Die beiden Datenbanken und die beiden Anwendungen davor, letztere, damit
# sie nicht in eine weggezogene Datenbank schreiben und mit Fehlern volllaufen.
# n8n, Caddy, Tika und Gotenberg bleiben oben: Sie halten keinen Zustand, der
# zu den Datenbanken passen müsste.
DIENSTE=(paper-werk-app paperless paper-werk-db paperless-db)

#: **Die Container kommen zurück, egal was passiert.**
#
# Ohne diese Falle bliebe der Stack unten, wenn der Snapshot scheitert, und
# das fiele erst am Morgen auf, wenn jemand arbeiten will. Ein
# fehlgeschlagenes Backup ist ärgerlich, ein Betrieb, der deswegen steht,
# ist ein Ausfall.
wieder_hoch() {
    local rc=$?
    log "Dienste wieder starten …"
    "${COMPOSE[@]}" start "${DIENSTE[@]}" >/dev/null 2>&1 \
        || warn "Start fehlgeschlagen - Stack von Hand prüfen!"
    [ "$rc" -eq 0 ] || warn "Die Sicherung ist gescheitert (Code $rc)."
    exit "$rc"
}
trap wieder_hoch EXIT

start=$(date +%s)
log "Dienste anhalten: ${DIENSTE[*]}"
"${COMPOSE[@]}" stop "${DIENSTE[@]}" >/dev/null 2>&1 \
    || die "Konnte die Dienste nicht stoppen"

log "Snapshot von $KOPIA_SOURCE_PATH …"
# **MSYS_NO_PATHCONV nur hier**, und das ist keine Feinheit: Git Bash unter
# Windows hält jedes Argument, das mit / anfängt, für einen Pfad und
# übersetzt es: Aus /source/paper-werk wird
# "C:/Program Files/Git/source/paper-werk", und Kopia sucht dann im Container
# nach einem Ordner, den es nie gab.
#
# Global gesetzt (etwa vor dem ganzen Skript) bricht dafür "docker compose
# stop": Auch dessen Pfadangaben laufen dann ungewandelt durch, und die
# Dienste bleiben oben. Beides einzeln beim Bauen erlebt. Die Variable
# gehört deshalb genau an diese eine Zeile.
#
# Auf Linux und macOS ist sie wirkungslos; dort gibt es keine
# Pfadkonvertierung, und eine unbekannte Variable stört nicht.
MSYS_NO_PATHCONV=1 docker exec "$KOPIA_CONTAINER" \
    kopia snapshot create "$KOPIA_SOURCE_PATH" \
    || die "Snapshot fehlgeschlagen"

log "Stillstand: $(( $(date +%s) - start )) s"
