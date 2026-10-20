#!/usr/bin/env bash
# Richtet die Paperless-Seite der gemeinsamen Anmeldung ein: die Gruppen, in
# die Microsoft Entra ID die Konten einsortiert, und die Freigabe des Archivs
# an diese Gruppen.
#
#   ./setup.sh --project ../config sso
#
# NICHT im Standardlauf von setup.sh: Nicht jede Installation hat ein
# Identitätsverzeichnis. Wer keins hat, braucht dieses Modul nicht.
#
# ── Warum es dieses Modul gibt ────────────────────────────────────────────────
#
# Die Anmeldung allein bringt niemanden an seine Dokumente. Paperless legt ein
# SSO-Konto ohne jedes Recht an (Fehlerbild: 403 auf /api/ui_settings/ gleich
# nach dem Login), und selbst mit Rechten sieht ein Benutzer nur, was ihm
# gehört, was keinen Eigentümer hat oder was ausdrücklich freigegeben ist.
# In einem Teststack gehörten alle Dokumente dem Konto admin, ebenso alle Tags, Korrespondenten, Dokumenttypen und Speicherpfade. Das
# ist kein Zufall der Testdaten: App und n8n laden mit dem Schlüssel von
# admin hoch, neue Dokumente gehören also auch künftig admin.
#
# Entschieden wurde deshalb "Freigabe an die Gruppe": Eigentümer bleibt admin,
# die Gruppen bekommen Lese- und Schreibzugriff. Der Satz für den Kunden:
# "Alles im Archiv ist fürs Büro freigegeben." Einzelnes lässt sich später
# wieder einschränken; das ginge bei eigentümerlosen Dokumenten nicht.
#
# Die Rolle paper-werk-superuser braucht hier nichts: Sie wird über
# PAPERLESS_SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP bei jeder Anmeldung zum
# Superuser gemacht (und ebenso wieder zurück, wenn Entra ihr die Rolle
# entzieht). Superuser sehen alles.
#
# ── Wiederholbar ──────────────────────────────────────────────────────────────
#
# Jeder Schritt ist idempotent: Die Gruppen werden über ihren Namen erkannt,
# ihre Rechte werden auf den Soll-Stand gesetzt, die Freigaben mit merge ergänzt
# statt ersetzt. Ein zweiter Lauf ändert nichts, und genau so holt man
# Stammdaten nach, die admin nach dem ersten Lauf angelegt hat. Die gibt der
# Workflow unten nämlich NICHT frei, er wirkt nur auf Dokumente.

set -euo pipefail
cd "$(dirname "$0")/.."
source lib/common.sh
load_conf
require_cmd curl jq

[ -n "${PAPERLESS_TOKEN:-}" ] || die "PAPERLESS_TOKEN fehlt in setup.conf"
paperless_bereit 30 2 || die "Paperless antwortet nicht (PAPERLESS_CONTAINER/PAPERLESS_URL in setup.conf prüfen)"

# Je App-Rolle in Entra eine Gruppe, mit GENAU dem Wert der Rolle als Namen
# (Feld "Value", nicht "Display name"). Paperless ordnet über
# Group.objects.filter(name__in=...) zu und legt dabei nichts an; bei einem
# Tippfehler bleibt das Konto still ohne Gruppe und sieht wieder nichts.
#
# Jede Rolle steht für sich: Eine Person bekommt im Portal genau eine, und
# jede dieser Gruppen sieht das ganze Archiv. Im Archiv unterscheiden sich
# Büro und Projektleitung nicht; der Unterschied liegt in paper-werk-app
# (gleichnamige Gruppen, siehe core/gruppen.py dort). paper-werk-superuser
# fehlt hier absichtlich: Die Rolle macht zum Superuser, siehe oben, und der
# sieht ohnehin alles.
read -r -a GRUPPEN <<<"${SSO_GRUPPEN:-paper-werk-buero paper-werk-projektleitung}"

# ── 1. Die Gruppen und ihre Rechte ───────────────────────────────────────────
#
# Arbeitsgruppen, nicht die Verwaltung. Enthalten ist, was man zum Ablegen,
# Suchen und Zuordnen braucht; nicht enthalten sind Workflows, Mailkonten,
# Benutzer, Gruppen und Systemeinstellungen.
#
# Dokumente LÖSCHEN dürfen sie nicht. Ein Archiv mit Belegen, die
# aufbewahrt werden müssen, ist kein Ort, an dem jeder Arbeitsplatz
# wegräumen kann; das bleibt der Verwaltung. Wer das anders will, ergänzt
# delete_document hier.
RECHTE='[
  "view_document","add_document","change_document",
  "view_note","add_note","change_note","delete_note",
  "view_tag","add_tag","change_tag",
  "view_correspondent","add_correspondent","change_correspondent",
  "view_documenttype","add_documenttype","change_documenttype",
  "view_storagepath",
  "view_customfield","view_customfieldinstance","add_customfieldinstance","change_customfieldinstance","delete_customfieldinstance",
  "view_savedview","add_savedview","change_savedview","delete_savedview",
  "view_savedviewfilterrule","add_savedviewfilterrule","change_savedviewfilterrule","delete_savedviewfilterrule",
  "view_sharelink","add_sharelink","change_sharelink","delete_sharelink",
  "view_sharelinkbundle","add_sharelinkbundle","change_sharelinkbundle","delete_sharelinkbundle",
  "view_uisettings","add_uisettings","change_uisettings",
  "view_paperlesstask",
  "view_global_statistics",
  "view_logentry"
]'

vorhanden=$(papi GET "/api/groups/?page_size=1000")
gids=()
for gruppe in "${GRUPPEN[@]}"; do
  gid=$(jq -r --arg n "$gruppe" '.results[] | select(.name == $n) | .id' <<<"$vorhanden")
  koerper=$(jq -cn --arg n "$gruppe" --argjson r "$RECHTE" '{name: $n, permissions: $r}')
  if [ -z "$gid" ]; then
    gid=$(papi POST "/api/groups/" "$koerper" | jq -r '.id')
    ok "Gruppe '$gruppe' angelegt (id $gid)."
  else
    # Rechte auf den Soll-Stand setzen, nicht ergänzen: Was hier nicht steht,
    # soll die Gruppe auch nicht haben.
    papi PUT "/api/groups/$gid/" "$koerper" >/dev/null
    ok "Gruppe '$gruppe' vorhanden (id $gid) - Rechte auf Soll-Stand gesetzt."
  fi
  gids+=("$gid")
done
gids_json=$(printf '%s\n' "${gids[@]}" | jq -s 'map(tonumber)')

freigabe=$(jq -cn --argjson g "$gids_json" \
  '{view: {users: [], groups: $g}, change: {users: [], groups: $g}}')

# ── 2. Den Bestand freigeben ─────────────────────────────────────────────────
#
# Stammdaten zuerst: Ein Dokument, das man sieht, dessen Tags man aber nicht
# sieht, lässt sich weder filtern noch zuordnen.
for typ in tags correspondents document_types storage_paths; do
  ids=$(papi GET "/api/$typ/?page_size=10000" | jq -c '[.results[].id]')
  n=$(jq 'length' <<<"$ids")
  if [ "$n" -eq 0 ]; then
    log "$typ: keine vorhanden"
    continue
  fi
  papi POST "/api/bulk_edit_objects/" "$(jq -cn --argjson o "$ids" --arg t "$typ" --argjson p "$freigabe" \
    '{objects: $o, object_type: $t, operation: "set_permissions", permissions: $p, merge: true}')" >/dev/null
  ok "$typ: $n freigegeben."
done

# Alle IDs auf einer Seite. Früher lieferte die Liste sie unter "all"
# unabhängig von der Seitengröße; Paperless 3.x tut das nicht mehr -
# "all" fehlt dort, und das Skript meldete bei 574 Dokumenten "keine
# vorhanden". Deshalb wird jetzt gegengezählt: Weicht die
# Zahl der gelieferten IDs von "count" ab, bricht der Lauf ab, statt einen
# Teil des Archivs still nicht freizugeben.
#
# Und es werden NUR die Dokumente geschickt, denen die Freigabe noch fehlt.
# Jede Rechteänderung über bulk_edit stößt in Paperless eine Aktualisierung
# der betroffenen Dokumente an (bulk_update_documents), und die ist teuer:
# 574 Dokumente hielten den Worker 406 Sekunden beschäftigt -
# und in der Zeit wird nichts eingelesen, der Posteingang steht. Ein Lauf, der
# alles schickt, legte also bei jeder Wiederholung das Archiv für Minuten
# lahm, auch wenn es nichts freizugeben gab. So stößt ein zweiter Lauf gar
# nichts an.
liste=$(papi GET "/api/documents/?page_size=100000&fields=id,permissions&full_perms=true")
n=$(jq '.results | length' <<<"$liste")
soll=$(jq '.count' <<<"$liste")
[ "$n" -eq "$soll" ] || die "Dokumente: $n geliefert, aber $soll vorhanden - Freigabe abgebrochen."
doc_ids=$(jq -c --argjson g "$gids_json" '[.results[]
  | select(($g - [.permissions.view.groups[]?] | length) > 0
        or ($g - [.permissions.change.groups[]?] | length) > 0)
  | .id]' <<<"$liste")
fehlend=$(jq 'length' <<<"$doc_ids")
if [ "$fehlend" -gt 0 ]; then
  papi POST "/api/documents/bulk_edit/" "$(jq -cn --argjson d "$doc_ids" --argjson p "$freigabe" \
    '{documents: $d, method: "set_permissions", parameters: {set_permissions: $p, merge: true}}')" >/dev/null
  ok "Dokumente: $fehlend von $n freigegeben (Paperless aktualisiert sie im Hintergrund)."
else
  log "Dokumente: alle $n bereits freigegeben - nichts zu tun"
fi

# Gespeicherte Ansichten ("Posteingang", "Rechnungen" ...), einzeln, weil
# bulk_edit_objects sie nicht kennt (nur tags, correspondents,
# document_types, storage_paths). Ein PATCH mit set_permissions ERSETZT die
# Freigaben der Ansicht; deshalb wird der Ist-Stand gelesen und die Gruppen
# dazugenommen, damit von Hand vergebene Freigaben stehen bleiben.
#
# Nur LESEN: Die Ansichten sind gemeinsame Einrichtung. Wer sie ändern will,
# legt sich eine eigene an.
#
# Was die Freigabe NICHT bewirkt: dass die Ansicht in der Seitenleiste steht.
# Das ist eine Einstellung je Benutzer (ui_settings), die nur der Benutzer
# selbst schreiben kann, für ein Konto, das es beim Setup noch gar nicht
# gibt, erst recht. Jeder schaltet sie einmal selbst ein: Einstellungen ->
# Gespeicherte Ansichten -> "In Seitenleiste anzeigen".
ansichten=$(papi GET "/api/saved_views/?page_size=1000&full_perms=true")
while read -r v; do
  [ -n "$v" ] || continue
  vid=$(jq -r '.id' <<<"$v")
  rechte=$(jq -c --argjson g "$gids_json" '{set_permissions: {
      view:   {users: [.permissions.view.users[]?],   groups: ([.permissions.view.groups[]?] + $g | unique)},
      change: {users: [.permissions.change.users[]?], groups: [.permissions.change.groups[]?]}}}' <<<"$v")
  papi PATCH "/api/saved_views/$vid/" "$rechte" >/dev/null
done < <(jq -c '.results[]' <<<"$ansichten")
ok "saved_views: $(jq '.results | length' <<<"$ansichten") zum Lesen freigegeben."

# ── 3. Neue Dokumente automatisch freigeben ──────────────────────────────────
#
# Auslöser "Dokument hinzugefügt" (type 2) greift für jeden Weg ins Archiv:
# Oberfläche, consume-Ordner, Mail, und den Upload der App beim
# Festschreiben.
#
# Anders als die Stammdaten wird der Workflow nicht ergänzt, sondern auf den
# Soll-Stand gebracht: Gibt es ihn schon, wird er gelöscht und neu angelegt.
# Sonst bliebe eine später hinzugekommene Gruppe draußen; der Workflow
# würde weiter nur an die alten Gruppen freigeben, ohne dass es auffiele.
# Er gehört diesem Modul und trägt keine Einstellungen, die jemand von Hand
# pflegt.
WF_NAME="Freigabe an die paper-werk-Gruppen"
wfs=$(papi GET "/api/workflows/?page_size=1000")
alt_id=$(jq -r --arg n "$WF_NAME" '.results[] | select(.name == $n) | .id' <<<"$wfs")
if [ -n "$alt_id" ]; then
  papi DELETE "/api/workflows/$alt_id/" >/dev/null
fi
papi POST "/api/workflows/" "$(jq -cn --arg n "$WF_NAME" --argjson g "$gids_json" '{
  name: $n, order: 0, enabled: true,
  triggers: [{type: 2, sources: [1,2,3], filter_filename: null}],
  actions: [{type: 1, assign_view_groups: $g, assign_change_groups: $g}]
}')" >/dev/null
ok "Workflow '$WF_NAME' auf Soll-Stand ($(jq -r 'join(", ")' <<<"$gids_json" | sed 's/^/Gruppen-IDs /'))."

ok "SSO-Seite von Paperless eingerichtet."
