# Eingangsrechnungen für die Vorführung

Fünf erfundene Rechnungen **an Elektro Hofmeister e.K.**, für den Belegweg
„Rechnung aus Paperless nach paper-werk". Drei sind E-Rechnungen (PDF mit
eingebettetem XML), zwei gewöhnliche PDF. Jede zeigt eine andere Wendung.

| Datei | Art | Was man daran sieht |
| --- | --- | --- |
| `wittmann-881477-e-rechnung.pdf` | E-Rechnung | **Der Regelfall.** Die Projektreferenz trifft 2026-014 (Ludwigsplatz). Alle Felder und die Projektnummer kommen aus dem XML, in paper-werk entstehen 5 Positionen. Der Mensch setzt nur „Paper-Werk senden". |
| `ladetechnik-3521-e-rechnung.pdf` | E-Rechnung | **Ohne Projektreferenz.** Die Felder kommen aus dem XML, die Projektnummer bleibt leer. Die Bestellung auf der Seite sagt, wohin es gehört: 2026-021 (Autohaus Brandmeier) von Hand eintragen. |
| `solar-isar-26-1093-e-rechnung.pdf` | E-Rechnung | **Ein neuer Lieferant.** paper-werk kennt „Solar-Großhandel Isar GmbH" nicht, legt ihn an und kennzeichnet ihn. Projekt 2026-031 (PV Schreinerei Gruber). |
| `zellner-2026-117.pdf` | PDF | **Kein XML.** Mistral liest den Text, auch „Ihr Projekt 2026-028". Braucht den Korrespondenten „Gerüstbau Zellner". |
| `wittmann-881502.pdf` | PDF | **Ohne Projekt.** Lagermaterial. Die Rechnung kommt unkontiert an, 235,40 € stehen in paper-werk als offener Rest. |

Alle fünf laufen von `rechnung-erkennen` bis „Paper-Werk gesendet“ durch,
mit dem Ergebnis aus der Tabelle.

## Ablauf in der Vorführung

1. PDF in Paperless ablegen (Consume-Ordner oder Hochladen).
2. Tag `rechnung-erkennen` setzen. Nach einigen Sekunden stehen die Felder
   da; bei den E-Rechnungen zusätzlich der Tag `E-Rechnung`.
3. Gegenprüfen, fehlende Projektnummer oder Korrespondenten ergänzen.
4. Tag `Paper-Werk senden` setzen. In paper-werk liegt die Eingangsrechnung mit
   Link zurück ins Archiv.

## Zweimal geht nicht

**Paperless nimmt dieselbe Datei kein zweites Mal an** (gleiche
Prüfsumme). Wer vorher probt, muss vor dem Termin in Paperless die
Dokumente löschen **und** in paper-werk die Eingangsrechnungen. Sonst
fehlt das Dokument, oder die E-Rechnung hängt schon an einer alten
Dokumentnummer (409).

## Kennzeichnung

Jede Rechnung trägt den Hinweis „Beispieldatei … kein Zahlungsbeleg, keine
Buchungsgrundlage", wie die Belege in `archivbelege/`.

## Neu erzeugen

Aus dem Wurzelverzeichnis von paper-werk-app:

```bash
uv run python ../paper-werk/demodaten/elektro-hofmeister/eingangsrechnungen/erzeuge_rechnungen.py
```

Das Skript liest jedes XML mit dem Leser der App gegen, bevor es schreibt.
Braucht GTK (für WeasyPrint), siehe `faktura/pdf.py`.
