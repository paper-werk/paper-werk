# Belege aus Paperless nach paper-werk

Wie eine fremde Rechnung aus dem Archiv in die Faktura kommt und warum sie
dort **kein zweites PDF** bekommt.

## Der Weg

```
Dokument kommt in Paperless an (Scan, Mail, Upload)
   │
   ├─ Tag "rechnung-erkennen" ruft  rechnung-parsen
   │     → fragt zuerst paper-werk: steckt eine E-Rechnung (XML) im PDF?
   │         ja:   Felder aus dem XML, Tag "E-Rechnung", kein Mistral
   │         nein: Mistral liest Nettobetrag, Gesamtbetrag, Rechnungsnummer,
   │               Rechnungsdatum, Projektnummer aus dem OCR-Volltext
   │     → schreibt sie in die Custom Fields des Dokuments
   │
   ├─ MENSCH prüft in der Inbox gegen und korrigiert, was falsch erkannt
   │  wurde. Stimmt alles: Tag "Paper-Werk senden" setzen.
   │
   ├─ Paperless-Arbeitsablauf ruft  paper-werk-eingangsrechnung
   │     ohne "E-Rechnung": liest die Felder, den Korrespondenten
   │                        → POST /api/v1/eingangsrechnungen/
   │     mit "E-Rechnung":  schickt das Original-PDF und die Projektnummer
   │                        → POST /api/v1/eingangsrechnungen/erechnung/
   │     → setzt den Tag auf "Paper-Werk gesendet"
   │
   └─ In paper-werk liegt eine Eingangsrechnung mit Link zurück ins Archiv.
```

**Der Mensch in der Mitte ist kein Übergangszustand.** Ein Sprachmodell liest
Beträge gut, aber nicht sicher; 1.758,00 und 1.758,08 unterscheiden sich um
ein Pixel. Was hier durchrutscht, landet ungeprüft in einer
Projektkalkulation und von dort in einer Rechnung an einen Bauherrn. Der
Tag ist die Unterschrift unter „ich habe hingesehen".

## Was in paper-werk entsteht

Eine **Eingangsrechnung** mit Kopfdaten, `paperless_id` und, wenn eine
Projektnummer mitkam, einer Position über den vollen Betrag.

**Kein PDF.** Das fremde Dokument liegt in Paperless; dort wurde es
aufgenommen, mit OCR gelesen und gesichtet. Eine zweite Kopie in der
Faktura wäre eine zweite Wahrheit über dasselbe Blatt Papier. Was bleibt,
ist die Kennung und daraus ein Verweis, den der Admin als „Dokument 463
ansehen" zeigt.

## E-Rechnungen

Seit paper-werk 0.1.3. Eine E-Rechnung (ZUGFeRD, Factur-X) ist ein PDF mit
eingebettetem XML. Darin stehen Nummer, Datum, Beträge, Lieferant und jede
Position maschinenlesbar. Texterkennung und Sprachmodell braucht es dafür
nicht, und raten muss niemand.

**Die Erkennung prüft das zuerst.** Der Ablauf „Rechnungsfelder erkennen"
ruft `rechnung-parsen`. Der holt das Original-PDF aus Paperless und fragt paper-werk
(`POST /api/v1/eingangsrechnungen/erechnung-pruefen/`). Ist es eine lesbare
E-Rechnung, kommen die Felder aus dem XML, dazu `Fällig am`. Die
Projektnummer nur, wenn die Projektreferenz der Rechnung eindeutig auf ein
laufendes Projekt zeigt. Das Dokument bekommt den Tag **`E-Rechnung`**.
Mistral wird in diesem Fall nicht gefragt, es geht also auch kein Text in
die Cloud.

**Der Mensch prüft trotzdem**, setzt die Projektnummer, wenn sie fehlt, und
setzt `Paper-Werk senden`. Der Übertrag sieht den Tag `E-Rechnung` und schickt
das Original-PDF statt der Felder
(`POST /api/v1/eingangsrechnungen/erechnung/`). paper-werk liest es selbst
und legt **alle Positionen** der Rechnung an, nicht nur eine Summenzeile.
Einen Korrespondenten braucht dieser Weg nicht, der Lieferant steht im XML.

**Was keine lesbare E-Rechnung ist, geht den gewohnten Weg:** ein PDF ohne
XML, eine UBL-Datei im PDF, eine Gutschrift. Dann liest Mistral, und es
gibt keinen Tag `E-Rechnung`.

**Warum das Original:** Die Archivfassung, die Paperless selbst erzeugt
(PDF/A), hat den XML-Anhang oft nicht mehr. Beide Workflows laden deshalb
`/api/documents/{id}/download/?original=true`.

## Die Workflows

### rechnung-parsen

Füllt an einer Rechnung die Felder für den Übertrag: erst aus einer
E-Rechnung (siehe oben), sonst per Mistral aus dem OCR-Volltext. Trigger:
Tag `rechnung-erkennen`, Ablauf „Rechnungsfelder erkennen" →
`POST /webhook/rechnung-parsen` mit `{"doc_url": "{doc_url}"}`. Die
Rechnungsfelder stehen als Vorgabe im Workflow; ein `felder`-Objekt wie bei
`felder-erkennen-mistral` geht auch.

**Gebaut wie `handschrift-ocr-titel-mistral`:** Der Workflow prüft am
Dokument selbst, ob er zuständig ist, setzt `wird bearbeitet`, schreibt die
Felder und räumt am Ende `rechnung-erkennen` und `wird bearbeitet` in
einem Aufruf weg (bei einer E-Rechnung kommt ihr Tag dazu). Paperless räumt
nichts selbst weg. So löst das Zurückschreiben der Felder den Ablauf nicht
erneut aus. Bricht ein Lauf ab, bleibt `wird bearbeitet` stehen: Fehler
beheben, den Tag entfernen, `rechnung-erkennen` neu setzen.

### felder-erkennen-mistral

Der allgemeine Feldleser, unabhängig von paper-werk. Liest Felder aus dem
OCR-Volltext. Welche Felder, bestimmt der Aufrufer, optional im
Webhook-Body:

```json
{
  "doc_url": "{doc_url}",
  "felder": {
    "Nettobetrag": "Der Rechnungsbetrag OHNE Umsatzsteuer, als Zahl mit Punkt.",
    "Gesamtbetrag": "Der Bruttobetrag inklusive Umsatzsteuer.",
    "Rechnungsnummer": "Die Rechnungsnummer des Lieferanten.",
    "Rechnungsdatum": "Das Rechnungsdatum im Format JJJJ-MM-TT.",
    "Projektnummer": "Die Projektnummer, z. B. 2026-042."
  }
}
```

Ohne `felder` gelten die eingebauten Vorgaben (Rechnungs-, Versicherungs-,
Projektnummer); bestehende Arbeitsabläufe laufen unverändert weiter.

**Der Grund für den Umbau:** Ein Ablauf für Laborrechnungen braucht andere
Felder als einer für Versicherungspost. Vorher hätte man dafür den
Workflow kopiert, und ab da zwei Prompts gepflegt.

Nach E-Rechnungen sieht er nicht. Das tut `rechnung-parsen`.

### paper-werk-eingangsrechnung

Übergibt das gesichtete Dokument. Trigger: `POST
/webhook/paper-werk-eingangsrechnung` mit `{"doc_url": "{doc_url}"}`.

| Was er liest | woher |
| --- | --- |
| Nettobetrag, Rechnungsnummer, Rechnungsdatum | Custom Fields (Pflicht) |
| Projektnummer | Custom Field (freiwillig) |
| Lieferant | **Korrespondent** des Dokuments |

Trägt das Dokument den Tag `E-Rechnung`, liest er davon nur die
Projektnummer und schickt das Original-PDF. Alles andere liest paper-werk
aus dem XML.

**Warum der Korrespondent und kein Textfeld:** Paperless pflegt ihn
ohnehin, und er ist die Stelle, an der die Schreibweise einmal festgelegt
wird. Aus „ISARTAL", „Isartal GmbH" und „Bodenlabor Isartal GmbH" würden sonst
drei Lieferanten, und jede Auswertung zerfiele in drei.

**Der Tag ist Auslöser, Fortschritt und Fehlerliste in einem.** Umgesetzt
wird er erst *nach* der Antwort von paper-werk: Bricht der Übertrag ab,
bleibt `Paper-Werk senden` stehen, und das Dokument ist weiterhin als offen
sichtbar.

## Was paper-werk antwortet

| | |
| --- | --- |
| **201** | neu übernommen |
| **200** | war schon da, Kopfdaten aktualisiert |
| **400** | unbekannte Projektnummer, oder kein Lieferant |
| **409** | schon weiterberechnet, hier ändert sich nichts mehr |

**Zweimal laufen ist erlaubt und erwünscht.** Wer in Paperless einen Betrag
korrigiert und den Tag zurücksetzt, findet die Korrektur in paper-werk
wieder. Was ein Mensch dort aufgeteilt hat, bleibt unberührt; steht die
Position schon auf einer Ausgangsrechnung (auch im Entwurf), wird gar
nichts mehr geändert.

**Bei der E-Rechnung** (`/erechnung/`) antwortet paper-werk genauso mit 201
oder 200, aber ein zweiter Lauf ändert nichts, denn das XML ist dasselbe.
Einzige Ausnahme: Kam die Rechnung beim ersten Mal ohne Projekt an und
steht jetzt eine Projektnummer am Dokument, werden die Positionen angelegt.
War dieselbe Rechnung schon im Admin hochgeladen, bekommt sie den Verweis
ins Archiv, statt ein zweites Mal zu entstehen. **400** heißt hier auch:
keine lesbare E-Rechnung. **409**: dieselbe Rechnung hängt schon an einem
anderen Paperless-Dokument, das Papier liegt also zweimal im Archiv.

## Einrichten

**1. In paper-werk:**

```bash
uv run python manage.py paperless_einrichten          # was fehlt, zeigen
uv run python manage.py paperless_einrichten --trocken
```

Legt die sechs Zusatzfelder, die drei Tags (`Paper-Werk senden`,
`Paper-Werk gesendet`, `E-Rechnung`) und den Dokumenttyp
`Eingangsrechnung` an. Ohne `--trocken` wird angelegt, mit nur gezeigt.

**2. Dienstbenutzer in paper-werk**: Verwaltung → Benutzer, dann
Verwaltung → API-Schlüssel. Zwei Rechte genügen:
`erfassung.add_eingangsrechnung` und `faktura.view_projekt`. Über eine
Gruppe vergeben, nicht am Benutzer: Der nächste Workflow braucht dieselben.

**3. In n8n:**

* Data Table `pw_config` → `paperwerk_url` eintragen. Im Stack der
  Docker-Servicename (`http://paper-werk-app:8000`), **nicht** die
  Browser-Adresse.
* Credential „Header Auth paper-werk" → `Token <der Schlüssel von oben>`.
* Workflow `paper-werk-eingangsrechnung` einmal von Hand ausführen, dann
  aktivieren.
* `rechnung-parsen` braucht dieselbe `paperwerk_url` und dieselbe
  Credential „Header Auth paper-werk", dazu „Header Auth paperless" und
  „Header Auth Mistral".

**4. In Paperless** zwei Arbeitsabläufe:

| Auslöser | ruft |
| --- | --- |
| Tag `rechnung-erkennen` gesetzt | `rechnung-parsen` |
| Tag `Paper-Werk senden` gesetzt | `paper-werk-eingangsrechnung` |

Beide stehen fertig im Starterpaket (`workflows.json`, Abläufe
„Rechnungsfelder erkennen (Mistral)" und „Eingangsrechnung an paper-werk").

## Wenn etwas schiefgeht

**Der Tag bleibt stehen.** Das ist die erste Fehlerliste: In Paperless nach
`Paper-Werk senden` filtern zeigt alles, was hängengeblieben ist.

**Die zweite steht in n8n** unter Ausführungen. Der Workflow zeigt auf
`fehler-melden` (`errorWorkflow: pwFehlerMelden01`) und schickt eine Mail
an `mail_betrieb`.

Häufige Fälle:

| Meldung | Ursache |
| --- | --- |
| „Am Dokument … fehlen: Nettobetrag" | Mistral hat nichts erkannt und niemand hat es nachgetragen |
| „hat keinen Korrespondenten" | in Paperless nicht gesetzt |
| „kein Zusatzfeld …" | `manage.py paperless_einrichten` lief nicht |
| 401 vom paper-werk-Aufruf | Token fehlt oder ist falsch |
| 400 „kein Vorhaben mit der Nummer" | Tippfehler im Feld, oder Projekt noch nicht angelegt |
| 400 „In diesem PDF steckt keine E-Rechnung" | Tag `E-Rechnung` von Hand an ein gewöhnliches PDF gesetzt. Tag entfernen, Felder prüfen, erneut übertragen |
| 409 „bereits aus dem Archivdokument … übernommen" | dieselbe E-Rechnung liegt zweimal in Paperless |
| „kein Schlagwort E-Rechnung" | `manage.py paperless_einrichten` lief vor 0.1.3 zuletzt |

## Was offen ist

* **Nur Eingangsrechnungen.** Ein unterschriebenes Angebot oder ein
  Lieferschein des Nachunternehmers ginge denselben Weg, ist aber
  schwerer: Beide haben Positionen, und die passen in kein Zusatzfeld.
* **E-Rechnungen nur als CII.** Eine UBL-Datei im PDF geht den Mistral-Weg.
* **Der Bruttobetrag wandert nicht mit.** paper-werk rechnet mit netto;
  brutto steht in Paperless und dient dem Menschen beim Gegenprüfen.
* Ob der Workflow bei 409 den Tag trotzdem umsetzen sollte. Derzeit nicht;
  das Dokument bleibt in der Liste, und jemand muss entscheiden, was mit
  der Änderung geschieht.
