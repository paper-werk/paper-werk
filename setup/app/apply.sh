#!/usr/bin/env bash
# Richtet paper-werk-app ein: Superuser, Rechtegruppen, Textbausteine,
# Dienstzugang und die Tags und Felder, die die App in Paperless braucht.
#
# Warum es dieses Modul gibt: Nach dem ersten Start steht eine Anwendung,
# in die niemand hineinkommt, weil Django keinen Benutzer anlegt. Paperless löst
# dasselbe über PAPERLESS_ADMIN_USER/_PASSWORD in seiner .env, die App tut das
# bewusst nicht: Ein Passwort in einer Datei, die der Container bei jedem Start
# liest, bleibt dort stehen. Hier wird es einmal benutzt und danach nicht mehr
# gebraucht.
#
# Das Modul heißt "app" und nicht "paper-werk-app". Im Setup ist eindeutig,
# welche gemeint ist; die anderen drei heißen paperless, n8n und kopia.
#
# Idempotent, und zwar in der wichtigen Richtung: Ein vorhandener Benutzer wird
# NICHT angefasst. Ein zweiter Lauf darf ein geändertes Passwort nicht
# zurückdrehen, sonst wäre jede Wiederholung des Setups eine stille
# Rücksetzung des Administratorkontos.

set -euo pipefail
cd "$(dirname "$0")/.."
source lib/common.sh
load_conf
require_cmd docker curl

[ -n "${APP_CONTAINER:-}" ] \
  || die "APP_CONTAINER ist nicht gesetzt (setup.conf) - ohne ihn weiß dieses Modul nicht, welchen Container es meint."

docker inspect "$APP_CONTAINER" >/dev/null 2>&1 \
  || die "App-Container '$APP_CONTAINER' nicht gefunden (APP_CONTAINER in setup.conf prüfen)"

# Der Container startet mit "migrate && gunicorn". Vor der ersten Migration
# gibt es die Benutzertabelle noch nicht, und createsuperuser liefe in einen
# Datenbankfehler. Das Lebenszeichen ist der einzige offene Endpunkt und
# antwortet erst, wenn Django wirklich steht.
#
# Gefragt wird IM Container (app_bereit in lib/common.sh), nicht über
# APP_URL: Im HTTPS-Betrieb hat die App keinen eigenen Port mehr.
log "Warte auf das Lebenszeichen der App (im Container $APP_CONTAINER) …"
app_bereit 60 2 \
  || die "Die App antwortet nicht - läuft der Stack? (docker compose ps; docker logs $APP_CONTAINER)"
ok "App erreichbar."

# manage.py im Container. `uv run --no-dev` ist derselbe Aufruf, den auch der
# Startbefehl des Images benutzt.
aexec() { docker exec "$APP_CONTAINER" uv run --no-dev python manage.py "$@"; }

# ── 1. Superuser ─────────────────────────────────────────────────────────────
[ -n "${APP_ADMIN_USER:-}" ] && [ -n "${APP_ADMIN_PASSWORD:-}" ] \
  || die "APP_ADMIN_USER und APP_ADMIN_PASSWORD müssen in setup.conf stehen."

# Die Antwort wird über eine Marke gelesen, nicht über die letzte Zeile:
# `manage.py shell` schreibt seit Django 5.2 eine Zeile über automatisch
# importierte Objekte, und `uv run` meldet bei Bedarf kompilierte Bytecodes.
# Beides stünde sonst mit im Ergebnis.
vorhanden=$(aexec shell -c "
from django.contrib.auth import get_user_model
print('MARKE:' + ('ja' if get_user_model().objects.filter(username='$APP_ADMIN_USER').exists() else 'nein'))
" 2>/dev/null | tr -d '\r' | sed -n 's/^MARKE://p')

case "$vorhanden" in
  ja)
    log "Benutzer '$APP_ADMIN_USER' existiert bereits - unverändert gelassen."
    log "  (Passwort wird bewusst nicht zurückgesetzt. Neues Passwort setzen:"
    log "   docker exec -it $APP_CONTAINER uv run --no-dev python manage.py changepassword $APP_ADMIN_USER)"
    ;;
  nein)
    log "Lege Superuser '$APP_ADMIN_USER' an …"
    docker exec -e DJANGO_SUPERUSER_PASSWORD="$APP_ADMIN_PASSWORD" "$APP_CONTAINER" \
      uv run --no-dev python manage.py createsuperuser --noinput \
        --username "$APP_ADMIN_USER" --email "${APP_ADMIN_EMAIL:-admin@example.invalid}" >/dev/null
    ok "Superuser angelegt."
    ;;
  *)
    die "Konnte nicht feststellen, ob '$APP_ADMIN_USER' existiert (Antwort: '${vorhanden:-leer}')."
    ;;
esac

# ── 2. Rechtegruppen ─────────────────────────────────────────────────────────
# Legt "Faktura" (Arbeitsgruppe) und "Faktura Dienst" (nur lesen) an und setzt
# ihre Rechte. Ohne diesen Schritt kann ein Buerokonto nichts tun und ein
# Dienstzugang bekommt auf jede Anfrage 403.
#
# Die Rechteliste steht im Quelltext der App neben den Modellen, zu denen sie
# gehört, nicht hier. Eine zweite Liste an dieser Stelle würde beim
# nächsten neuen Modell vergessen.
log "Setze Rechtegruppen …"
aexec faktura_rechte
# Zweiter Befehl, weil es zwei Rollen sind: faktura_rechte deckt Angebote und
# Rechnungen ab, erfassung_rechte die Leistungserfassung.
# Jeder filtert auf seine eigenen app_labels; wer eines Tages nur eine der
# beiden ausliefert, ruft nur den einen auf.
aexec erfassung_rechte
ok "Gruppen eingerichtet."

# ── 3. Textbausteine ─────────────────────────────────────────────────────────
# Anrede, Einleitungen, Grussformel und die Mail-Anschreiben je Belegart. Ohne
# sie steht ein Büro vor leeren Auswahllisten.
#
# Der Wortlaut steht in paper-werk-app (faktura/standardtexte.py), nicht hier -
# dieselbe Regel wie bei den Rechtegruppen. Der Befehl überschreibt nichts,
# was es unter einem Namen schon gibt; ein umformulierter Baustein bleibt also
# auch beim zweiten Lauf so, wie der Betrieb ihn geschrieben hat.
#
# Die Grussformel trägt den Firmennamen. Existiert noch keine Firma (der
# Regelfall beim ersten Setup), entsteht sie ohne Namenszeile; der Befehl
# sagt dann, wie man das nachholt. Ein Demobestand zieht den Namen selbst nach.
log "Lege Textbausteine an …"
aexec faktura_textbausteine
ok "Textbausteine eingerichtet."

# ── 4. Dienstzugang für n8n ─────────────────────────────────────────────────
# Das Gegenstück zum PAPERLESS_TOKEN: ein Konto ohne Passwort und ohne
# Admin-Zugang, das sich ausschließlich über seinen Schlüssel ausweist. Es
# kommt in "Faktura Dienst" (Belegabholung) und "Belegübernahme"
# (Eingangsrechnungen), die Vorgabe von api_schluessel.
# Leer lassen in setup.conf überspringt den Schritt.
if [ -n "${APP_DIENSTZUGANG:-}" ]; then
  log "Richte Dienstzugang '$APP_DIENSTZUGANG' ein …"
  aexec api_schluessel "$APP_DIENSTZUGANG" --anlegen
  warn "Der Schlüssel steht oben. Er gehört in die n8n-Credential für die App -"
  warn "dasselbe Verfahren wie bei Paperless (Header Auth, 'Authorization: Token <key>')."
else
  log "APP_DIENSTZUGANG ist leer - kein Dienstzugang angelegt."
fi

# ── 5. Was die App in Paperless braucht ─────────────────────────────────────
# Die Tags "Paper-Werk senden" und "Paper-Werk gesendet", die Felder
# "Rechnungsdatum" und "Nettobetrag", der Dokumenttyp "Eingangsrechnung".
# Die Namen stehen in paper-werk-app (paperless_einrichten), nicht im
# Starterpaket, dieselbe Regel wie bei Rechtegruppen und Textbausteinen.
#
# Muss VOR dem Modul paperless laufen: Dessen Workflow "Eingangsrechnung an
# paper-werk" verweist auf den Tag "Paper-Werk senden" und bricht ohne ihn ab.
# Die Standardreihenfolge von setup.sh (app vor paperless) hält das ein.
#
# Ohne diesen Schritt läuft eine frische Anlage im Modul paperless auf
# "Unbekannt (Tag): Paper-Werk senden".
#
# Kein Abbruch, wenn es scheitert: Der häufigste Grund ist ein
# PAPERLESS_TOKEN, der noch nicht in .env.app steht (Kundeninstallation.md,
# Abschnitt 5). Superuser, Gruppen und Dienstzugang stehen dann schon, und
# ein zweiter Lauf dieses Moduls holt den Rest nach.
log "Richte in Paperless ein, was die App braucht …"
if aexec paperless_einrichten; then
  ok "Paperless für die App eingerichtet."
else
  warn "paperless_einrichten ist gescheitert - die Meldung steht darüber."
  warn "Danach: bash setup.sh --project $PROJECT_DIR app paperless"
fi

ok "paper-werk-app eingerichtet."
