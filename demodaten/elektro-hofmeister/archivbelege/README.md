# Papierbelege für das Archiv

Sieben erfundene Belege, wie sie bei einem Elektrobetrieb hereinkommen. Zum
Einwerfen in Paperless, für **Pfad A** der Vorführung: *„wir haben ein
Archiv"*.

## Warum es sie gibt

Was der Bestand `elektro-hofmeister` erzeugt, sind ausschließlich **Ausgangsbelege**:
Angebote, Rechnungen, Mahnungen, die beim Festschreiben ins Archiv gelegt
werden. Wer mit dem Archiv beginnt, braucht dafür eingehende Belege.

Sie decken zugleich die Dokumenttypen ab, die das Starterpaket `elektro`
mitbringt (Prüfprotokoll, Netzanmeldung, Lieferschein). Ohne sie stünden die
Typen leer da und niemand wüsste, wofür sie gedacht sind.

## Die Belege

| Datei | Was daran zu sehen ist |
| --- | --- |
| `tankquittung-2026-08-19.pdf` | Der Kleinbeleg, den jeder kennt. Zwei Positionen, Bruttobetrag, ausgewiesene USt: der Regelfall für die Belegerfassung. |
| `mietvertrag-werkstatt.pdf` | **Ein Vertrag, der Jahre trägt.** Fünf Jahre Laufzeit, sechs Monate Kündigungsfrist, also das, wofür die Felder *Vertragsende*, *Kündigungsfrist* und *Kündigen bis* aus dem Basispaket da sind. |
| `versicherung-betriebshaftpflicht-2026.pdf` | Jahresbeitrag mit Fälligkeit. Deckt Ladeeinrichtungen und PV ab, passend zu den Projekten im Bestand. |
| `hwk-beitragsbescheid-2026.pdf` | **Ein Bescheid mit Frist.** Rechtsbehelfsbelehrung, ein Monat Widerspruch. Der Fall, bei dem Wiedervorlage kein Komfort ist. |
| `lieferschein-wittmann-880366.pdf` | Gehört zur E-Rechnung `wittmann-880366-material.xml`: **dieselben vier Positionen, dieselbe Rechnungsnummer**. Zeigt im Termin, wie Lieferschein und Rechnung im Archiv zusammenfinden. |
| `pruefprotokoll-dguv-v3-bauhof.pdf` | **Der Beleg, der das Gewerk ausmacht.** 218 geprüfte Geräte, vier mit Mangel, nächste Prüfung in einem Jahr. Passt zur Prüfrechnung an die Gemeinde Altdorf aus dem Bestand. |
| `netzanmeldung-wallbox-autohaus.pdf` | Ohne sie läuft keine Wallbox. Trägt die **Seriennummern** aus `ladetechnik-3402-wallbox.xml` und die Zählernummer und zeigt einen Vorgang, der noch nicht fertig ist: vier Ladepunkte in Prüfung. |

## Was daran nicht verhandelbar ist

Jeder Beleg trägt den Hinweis **„Beispieldatei … kein Zahlungsbeleg, keine
Buchungsgrundlage"**. Diese Dateien sehen aus wie echte Belege und liegen in
einem Archiv neben echten; ohne die Kennzeichnung wäre der Tag absehbar, an
dem eine davon in einer Buchhaltung landet. Ein Test hält das fest.

## Neu erzeugen

```bash
uv run --project ../paper-werk-app python \
    demodaten/elektro-hofmeister/archivbelege/erzeuge_belege.py
```

Braucht GTK (für WeasyPrint), siehe die Erklärung in `faktura/pdf.py`.

**Die Dateien sind byte-genau wiederholbar**, und das war nicht umsonst zu
haben: Beim ersten Lauf ergaben zwei Durchgänge hintereinander sieben
verschiedene Dateien, weil WeasyPrint die Erzeugungszeit ins PDF stempelt.
Der Inhalt war jedesmal derselbe, die Datei nicht; jeder Lauf hätte eine
Änderung im Repo erzeugt, ohne dass sich etwas geändert hätte. Das Skript
setzt deshalb `SOURCE_DATE_EPOCH` selbst; zwei Läufe ergeben dieselben
Prüfsummen.

## In Paperless einspielen

Über den Consume-Ordner, so wie es ein Kunde auch täte:

```bash
cp demodaten/elektro-hofmeister/archivbelege/*.pdf "$PAPER_WERK_DATA_ROOT/consume/"
```

Paperless zieht sie von selbst ein, die Arbeitsabläufe des Starterpakets
greifen darauf. Danach sind sie über die gespeicherten Ansichten zu finden:
*Prüfprotokolle*, *Material und Lieferanten*, *Beim Netzbetreiber*.
