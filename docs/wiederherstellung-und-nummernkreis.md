# Wiederherstellung und Nummernkreis

Gilt für jede Installation mit `paper-werk-app`.

## Das Problem

Die Sicherung läuft täglich (`setup/kopia/sicherung.sh`). Ein Restore setzt deshalb **beide
Datenbanken auf den Stand der letzten Nacht** zurück, auch den Zähler der Belegnummern
(`django-sequences`).

Beispiel: Ausfall um 15 Uhr, Restore der Sicherung von 2 Uhr.

| | vor dem Ausfall | nach dem Restore |
|---|---|---|
| Letzte Rechnung | RE-2026-0058 (heute versendet) | RE-2026-0055 |
| Nächste Nummer | 0059 | **0056, ein zweites Mal** |

Die Rechnungen 0056 bis 0058 sind beim Kunden, ihre PDFs meist auch im Archiv (hochgeladen beim
Festschreiben); nur die Anwendung weiß nichts mehr von ihnen. **Doppelt vergebene
Rechnungsnummern sind ein Befund beim Betriebsprüfer.**

Ein Restore-Test zeigt das nur, wenn zwischen Sicherung und Restore etwas
festgeschrieben wurde.

## Was nach jedem Restore zu tun ist

**Bevor irgendjemand wieder arbeitet:**

1. Letzte Nummer je Nummernkreis in der Anwendung feststellen.
2. Dagegen halten, was es seit dem Sicherungszeitpunkt gibt:
   * Paperless: Dokumente vom Typ `Rechnung`, hinzugefügt nach dem Sicherungszeitpunkt
     (sofern das Archiv nicht mit zurückgesetzt wurde oder aus einer jüngeren Quelle stammt),
   * gesendete Mails im Postfach des Absenders (Kopie an die Firmenadresse ist Vorgabe),
   * Übergaben an DATEV/Steuerbüro.
3. Fehlende Belege **neu erfassen und mit ihrer ursprünglichen Nummer festschreiben** oder, wenn
   das nicht möglich ist, den Zähler auf die höchste vergebene Nummer setzen und die Lücke in
   der Verfahrensdokumentation vermerken.

Ein Werkzeug dafür (Abgleich Zähler ↔ Archiv, Warnung beim Start nach Restore) gibt es noch
nicht.

## Die eigentliche Lösung: RPO in Minuten

Laufende Sicherung des Datenbank-Logs (WAL) mit den im Postgres-Image enthaltenen Werkzeugen
`pg_basebackup` und `pg_receivewal`, dazu Kopia in kurzen Abständen. Dann liegt der Zähler nach
einem Restore höchstens Minuten zurück, und beide Datenbanken lassen sich auf denselben Zeitpunkt
setzen.

**Auch dann bleibt Schritt 2 oben Pflicht**, nur mit viel weniger Arbeit.

## Offen

* Abgleich-Werkzeug bauen (`manage.py pruefe_nummernkreise` o. ä.).
* WAL-Sicherung auf einer Wegwerfinstallation aufbauen und die tatsächliche Datenmenge messen.
* Restore-Test wiederholen, diesmal **mit** Festschreibungen zwischen Sicherung und Restore.
