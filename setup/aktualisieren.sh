#!/usr/bin/env bash
# Bringt eine Installation auf den aktuellen Stand, in einem Befehl.
#
#   ./setup/aktualisieren.sh                  die Installation in config/
#   ./setup/aktualisieren.sh kunde              eine benannte unter config-repos/
#   ./setup/aktualisieren.sh kunde --ohne-sicherung   # nur für Testinstallationen
#   ./setup/aktualisieren.sh kunde --mit-setup        # Starterpaket erneut einspielen
#   ./setup/aktualisieren.sh kunde --trocken          # nur zeigen, was geschähe
#
# Der Ablauf, und warum er so herum ist:
#
#   1. Zustand prüfen. Ist an den ausgelieferten Dateien etwas geändert,
#      bricht der Lauf ab; ein `git pull` würde daraus einen Konflikt
#      machen, und zwar mitten im Update.
#   2. Sichern. Kopia-Snapshot bei stehenden Datenbanken, wenn Kopia läuft.
#      Ein Update, das sich nicht zurücknehmen lässt, ist kein Update.
#   3. Neuen Stand holen (git pull --ff-only), für dieses Repo, für den
#      Quelltext der Anwendung daneben (../paper-werk-app) und für die
#      Zusatz-Repos, die instanz.conf unter ZUSATZREPOS nennt.
#   4. Images holen und die Anwendung neu bauen, dann hochfahren. Migrationen
#      laufen beim Start der Container selbst.
#   5. Nachsehen, ob alles steht (setup/doktor.sh).
#
# **Was dieses Skript NICHT tut:** das Starterpaket erneut einspielen. Neue
# Tags, Dokumenttypen oder Workflows kommen nicht von allein in eine laufende
# Installation; dafür `--mit-setup`, und das gehört auf einen Zeitpunkt, an
# dem jemand hinsieht. Die Module sind idempotent, legen also nur an, was
# fehlt; n8n überschreibt vorhandene Workflows ausdrücklich nicht.
#
# Gedacht für die Installationen, an denen niemand etwas anfasst. Bei einem
# Kunden mit eigenem Systembetreuer ist Schritt 1 der wichtigste: Er sagt,
# ob dort jemand war.

set -euo pipefail
cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

blau=$'\033[1;34m'; gruen=$'\033[1;32m'; rot=$'\033[1;31m'; aus=$'\033[0m'
schritt() { printf '\n%s── %s %s\n' "$blau" "$*" "$aus"; }
ende()    { printf '%s[Fehler]%s %s\n' "$rot" "$aus" "$*" >&2; exit 1; }

name=""; sicherung=ja; mit_setup=nein; trocken=nein
while [ $# -gt 0 ]; do
  case "$1" in
    --ohne-sicherung) sicherung=nein; shift ;;
    --mit-setup)      mit_setup=ja;   shift ;;
    --trocken)        trocken=ja;     shift ;;
    -*) ende "Unbekannte Angabe: $1" ;;
    *)  name="$1"; shift ;;
  esac
done
# shellcheck source=lib/installation.sh
source setup/lib/installation.sh
if [ -n "$name" ] && ! ist_installation "$name"; then ende "Keine Installation: $name"; fi
ordner="$(installationsordner "$name")" \
  || ende "Aufruf: ./setup/aktualisieren.sh [<installation>] [--ohne-sicherung] [--mit-setup] [--trocken]; ohne Namen gilt config/, und das fehlt."
# Aufrufe von stack.sh und doktor.sh: mit Namen nur, wenn einer angegeben ist.
wahl=(); [ -n "$name" ] && wahl=("$name")
stack=(./stack.sh "${wahl[@]}")

tu() {
  if [ "$trocken" = ja ]; then printf '   würde laufen: %s\n' "$*"
  else printf '   %s\n' "$*"; "$@"; fi
}

# ── 1. Zustand ───────────────────────────────────────────────────────────────

schritt "Zustand vor dem Update"
abweichung="$(git -C "$WURZEL" status --porcelain -- compose config-template setup n8n starterpakete 2>/dev/null | grep -v '^??' || true)"
if [ -n "$abweichung" ]; then
  printf '%s\n' "$abweichung"
  ende "An ausgelieferten Dateien wurde gearbeitet. Erst klären, dann aktualisieren:
    ./setup/doktor.sh ${name}
  Sollen die Änderungen bleiben, gehören sie nach $ordner/compose.override.yml.
  Sollen sie weg: git restore compose config-template setup n8n starterpakete"
fi
printf '   %sausgelieferte Dateien unverändert%s\n' "$gruen" "$aus"

# Der Quelltext der Anwendung liegt im Nachbar-Repo; ohne dessen Pull baut
# Schritt 4 den alten Stand neu.
# Derselbe Ort wie in stack.sh: .env gewinnt, sonst neben diesem Repo.
app="$(sed -n 's/^[[:space:]]*PAPER_WERK_APP_CONTEXT=//p' "$ordner/.env" 2>/dev/null | tail -1 | tr -d '"'\''\r')"
if [ -z "$app" ]; then
  app="$WURZEL/../paper-werk-app"
elif [ "${app#/}" = "$app" ] && [ "${app#?:}" = "$app" ]; then
  app="$WURZEL/$ordner/$app"     # relativ: Compose löst gegen den Projektordner auf
fi
if git -C "$app" rev-parse --git-dir >/dev/null 2>&1; then
  abweichung="$(git -C "$app" status --porcelain 2>/dev/null | grep -v '^??' || true)"
  if [ -n "$abweichung" ]; then
    printf '%s\n' "$abweichung"
    ende "Im Quelltext der Anwendung ($app) wurde gearbeitet. Erst klären, dann aktualisieren."
  fi
  printf '   %sAnwendung unverändert%s (%s)\n' "$gruen" "$aus" "$app"
else
  printf '   Anwendung ist kein Git-Ordner (%s) - wird nicht geholt\n' "$app"
  app=""
fi

# Das Config-Repo der Installation (config/ oder config-repos/paper-werk-config-<name>),
# falls der Ordner eines ist. Geprüft wird auf ein eigenes .git im Ordner:
# Sonst fände git das Install-Repo darüber. Lokale Änderungen an versionierten Dateien brechen ab
# wie bei den anderen Repos; .env* sind dort ignoriert und zählen nicht.
config=""
if [ -e "$ordner/.git" ]; then
  config="$(cd "$ordner" && pwd)"
  abweichung="$(git -C "$config" status --porcelain 2>/dev/null | grep -v '^??' || true)"
  if [ -n "$abweichung" ]; then
    printf '%s\n' "$abweichung"
    ende "Im Config-Repo ($config) wurde gearbeitet. Erst committen und pushen oder verwerfen, dann aktualisieren."
  fi
  printf '   %sConfig-Repo unverändert%s (%s)\n' "$gruen" "$aus" "$config"
fi

# Zusatz-Repos (instanz.conf, ZUSATZREPOS): Apps, die per Bind-Mount in den
# App-Container kommen, etwa ein kundenspezifisches Repo. Pfade relativ zum
# Projektordner, wie in den Compose-Dateien. Ohne Eintrag passiert hier
# nichts. Ein genanntes Repo, das fehlt, ist ein Abbruch: Docker legte den
# Mount-Ordner sonst leer an, und die App startete nicht.
zusatzrepos="$( ZUSATZREPOS=""; [ -f "$ordner/instanz.conf" ] && source "$ordner/instanz.conf" >/dev/null 2>&1; printf '%s' "$ZUSATZREPOS" )"
zusatz=()
for z in $zusatzrepos; do
  pfad="$WURZEL/$ordner/$z"
  git -C "$pfad" rev-parse --git-dir >/dev/null 2>&1     || ende "In instanz.conf steht ZUSATZREPOS=\"$z\", aber dort liegt kein Git-Repo: $pfad"
  abweichung="$(git -C "$pfad" status --porcelain 2>/dev/null | grep -v '^??' || true)"
  if [ -n "$abweichung" ]; then
    printf '%s
' "$abweichung"
    ende "Im Zusatz-Repo ($pfad) wurde gearbeitet. Erst klären, dann aktualisieren."
  fi
  printf '   %sZusatz-Repo unverändert%s (%s)
' "$gruen" "$aus" "$pfad"
  zusatz+=("$pfad")
done

# ── 2. Sicherung ─────────────────────────────────────────────────────────────

schritt "Sicherung"
if [ "$sicherung" = nein ]; then
  printf '   übersprungen (--ohne-sicherung)\n'
# Über stack.sh, nicht über den Containernamen: Der Projektname steht in
# instanz.conf und ist nicht immer der Ordnername (kunde läuft als
# paper-werk-kunde).
elif [ -n "$("${stack[@]}" ps -q --status running kopia 2>/dev/null)" ]; then
  tu ./setup/kopia/sicherung.sh "$ordner"
else
  printf '   kein laufender Kopia-Container für "%s".\n' "$(anzeigename "$name")"
  printf '   %sOhne Sicherung gibt es keinen Weg zurück.%s Weiter nur, wenn das gewollt ist\n' "$rot" "$aus"
  printf '   (Testinstallation): erneut mit --ohne-sicherung aufrufen.\n'
  [ "$trocken" = ja ] || exit 1
fi

# ── 3. Neuer Stand ───────────────────────────────────────────────────────────

schritt "Neuen Stand holen"
if git -C "$WURZEL" rev-parse '@{upstream}' >/dev/null 2>&1; then
  tu git -C "$WURZEL" pull --ff-only
else
  printf '   kein Gegenstück im Netz eingetragen - übersprungen\n'
fi
if [ -n "$app" ]; then
  if git -C "$app" rev-parse '@{upstream}' >/dev/null 2>&1; then
    tu git -C "$app" pull --ff-only
  else
    printf '   Anwendung: kein Gegenstück im Netz eingetragen - übersprungen\n'
  fi
fi
if [ -n "$config" ]; then
  if git -C "$config" rev-parse '@{upstream}' >/dev/null 2>&1; then
    tu git -C "$config" pull --ff-only
  else
    printf '   Config-Repo: kein Gegenstück im Netz eingetragen - übersprungen\n'
  fi
fi

# Ein Zusatz-Repo ist eingehängt, nicht eingebaut: Neuer Code wirkt erst
# nach einem Neustart des App-Containers, und den macht Schritt 4 nur, wenn
# sich das Image geändert hat.
neustart=nein
for pfad in ${zusatz[@]+"${zusatz[@]}"}; do
  if ! git -C "$pfad" rev-parse '@{upstream}' >/dev/null 2>&1; then
    printf '   Zusatz-Repo: kein Gegenstück im Netz eingetragen - übersprungen (%s)
' "$pfad"
    continue
  fi
  vorher="$(git -C "$pfad" rev-parse HEAD)"
  tu git -C "$pfad" pull --ff-only
  [ "$(git -C "$pfad" rev-parse HEAD)" = "$vorher" ] || neustart=ja
done

# ── 4. Bauen und hochfahren ──────────────────────────────────────────────────

schritt "Images holen, bauen, hochfahren"
tu "${stack[@]}" pull --ignore-buildable
tu "${stack[@]}" up -d --build
if [ "$neustart" = ja ]; then
  tu "${stack[@]}" restart paper-werk-app
elif [ "$trocken" = ja ] && [ ${#zusatz[@]} -gt 0 ]; then
  printf '   würde laufen, falls ein Zusatz-Repo Neues bringt: %s restart paper-werk-app
' "${stack[*]}"
fi

# ── 5. Starterpaket (nur auf Wunsch) ─────────────────────────────────────────

if [ "$mit_setup" = ja ]; then
  schritt "Starterpaket nachziehen"
  tu ./setup/setup.sh --project "../$ordner"
fi

# ── 6. Nachsehen ─────────────────────────────────────────────────────────────

schritt "Zustand nach dem Update"
[ "$trocken" = ja ] || ./setup/doktor.sh "${wahl[@]}"
