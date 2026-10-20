# Demobestände

Hier stehen die erfundenen Betriebe für Vorführungen und Tests: Kunden,
Projekte, Rechnungen, erfasste Stunden. **Nichts davon liegt im Produkt.**
Eine Kundeninstallation von `paper-werk-app` enthält keine Demodaten, und
auch kein Programm, das welche anlegen könnte.

Eingespielt wird ein Bestand aus der Wurzel von paper-werk mit:

```bash
./demodaten/einspielen.sh config-repos/paper-werk-config-dev elektro-hofmeister
```

Lader (`laden.py`) und Aufruf (`einspielen.sh`) liegen hier neben den
Beständen und nicht in paper-werk-app.

**Das gilt für eine nackte, frische Installation.** Kein Nachladen, kein
Zusammenführen, kein Fortschreiben; auf einem gefüllten Bestand gibt es
doppelte Kunden oder einen Abbruch. Vor einem zweiten Lauf gehört die
Datenbank geleert. Das ist bewusst so: Ein Vorführbestand will *ein Zustand*
sein, jederzeit von null reproduzierbar, und nicht eine gewachsene Historie.

## Was hier liegt

| Verzeichnis | |
| --- | --- |
| `muster/` | der kleinste Bestand, an dem jede Bauform einmal vorkommt; die Vorlage für einen neuen |
| `elektro-hofmeister/` | Handwerksbetrieb, viele Kleinaufträge |
| `ingenieurbuero/` | Planer, Architekten, Gutachter: wenige große Vorhaben über Monate, Zukauf von Analytik, Abrechnung über Abschläge bis zur Schlussrechnung mit Absetzung |

## Wie ein Bestand aufgebaut ist

Ein Verzeichnis mit nummerierten JSON-Dateien. **Die Nummer ist die
Reihenfolge, der Name ist die Art**: `04-kunden.json` legt Kunden an, und
zwar nach `02-katalog.json`. Die Reihenfolge ist fachlich zwingend: ohne
Katalog kein Beleg, ohne Kunde kein Projekt.

| Datei | Was darin steht |
| --- | --- |
| `NN-betrieb.json` | die eigene Firma, ein Objekt, keine Liste |
| `NN-katalog.json` | Leistungen mit Preis und Einheit |
| `NN-mannschaft.json` | Personen und ihre Kostensätze |
| `NN-kunden.json` | Kunden |
| `NN-lieferanten.json` | Lieferanten |
| `NN-kleinauftraege.json` | Rechnungen **ohne** Projekt, direkt an den Kunden |
| `NN-projekte.json` | Projekte mit Auftrag, Erfassung und Rechnungen |
| `NN-abrechnungen.json` | Rechnungen **aus erfassten Leistungen**, nach dem Einkauf |
| `NN-zahlungen.json` | Zahlungseingänge auf gestellte Rechnungen, **ans Ende** |
| `NN-textbausteine.json` | Textbausteine des Gewerks, **zusätzlich** zu den Standardtexten |

### Kunden: flach bleibt flach

Ein Kunde besteht in der Anwendung aus vier Tabellen: er selbst, seine
Anschriften, seine Ansprechpartner, seine Kontaktwege. **Im Bestand merkt
man davon nichts:** `strasse`, `plz`, `ort`, `land`, `email` und `telefon`
stehen weiterhin direkt am Eintrag, und der Lader verteilt sie.

Wer mehr braucht, hängt zwei Listen an:

```json
{
  "nummer": "K-2003", "name": "Landratsamt Musterstadt",
  "email": "poststelle@lra.example",
  "adressen": [
    { "verwendung": "rechnung", "bezeichnung": "Rechnungsprüfung",
      "zusatz": "Zentrale Rechnungsprüfung",
      "strasse": "Am Alten Viehmarkt 3", "plz": "84028", "ort": "Landshut",
      "ist_standard": true },
    { "verwendung": "post", "strasse": "Veitsbucher Straße 2",
      "plz": "84032", "ort": "Musterstadt" }
  ],
  "leute": [
    { "anrede": "herr", "titel": "Dr.", "vorname": "Michael",
      "nachname": "Ostermeier", "funktion": "Wasserwirtschaft",
      "ist_standard": true, "email": "m.ostermeier@lra.example",
      "telefon": "0871 408-2215" }
  ]
}
```

**Wer `adressen` benutzt, lässt `strasse` oben weg.** Sonst entsteht daraus
eine zusätzliche Standardanschrift, und der Betrieb hat drei Adressen, wo er
zwei hat.

`verwendung` ist `rechnung`, `post`, `lieferung` oder `sonstige`; `anrede`
ist `frau`, `herr` oder leer (dann wird neutral angeschrieben). Der Eintrag
mit `"ist_standard": true` ist der, der gilt, wenn keiner genannt wird -
genau einer je Kunde. Wer keinen setzt, bekommt den ersten.

### Abrechnungen

Die Rechnungen unter `rechnungen` im Projekt haben eigene Positionen und
Preise; an ihnen hängt keine erfasste Zeit. Eine **Abrechnung** entsteht
dagegen so, wie sie im Betrieb entsteht: über „Erbrachte Leistungen
hinzufügen“. Danach hängen Zeiten und Fremdleistungen an der
Rechnungsposition, und die Akten zeigen je Auftragsposition, auf welcher
Rechnung sie steht.

```json
{
  "projekt": "{jahr}-070",
  "stunden_vor_tagen": [30, 19],
  "einkauf": ["AL-2026-09117"],
  "betreff": "Gutachten Stützmauer Nord - 1. Rechnung",
  "vor_tagen": 18
}
```

`stunden_vor_tagen` ist ein Zeitfenster **[von, bis]**: Alle noch offenen,
abrechenbaren Zeilen des Projekts aus diesen Tagen gehen mit. `einkauf`
nennt Eingangsrechnungen über ihre Nummer, ihre Fremdleistungen zu diesem
Projekt gehen mit. Leistungsdatum und -zeitraum kommen aus den Tagen der
Zeilen. `"entwurf": true` lässt die Rechnung als Entwurf stehen, sonst
wird sie mit dem Datum aus `vor_tagen` festgeschrieben.

**Die Tage im Projekt in Blöcken zu je drei legen.** Der Lader lässt
Wochenenden still weg. Ein Fenster mit nur einem Tag bleibt dann manchmal
leer, und eine leere Abrechnung bricht den Lauf ab.

### Zahlungen

Ohne sie steht in den offenen Posten jede jemals gestellte Rechnung, als
hätte der Betrieb seit einem Jahr kein Geld bekommen.

```json
{
  "kunde": "Landratsamt Musterstadt",
  "zahlername": "Landratsamt Musterstadt, Kreiskasse",
  "vor_tagen": 280,
  "verwendungszweck": "Sammelüberweisung 2 Rechnungen",
  "zuordnungen": [
    { "rechnung": "Schlussrechnung {jahr}-103 - Schadstoffkataster" },
    { "rechnung": "Schlussrechnung {jahr}-104 - Deklaration Bodenaushub" }
  ]
}
```

**Verwiesen wird über den Betreff** und nicht über die Belegnummer, nach
derselben Regel wie bei den Mahnungen und aus demselben Grund: Die Nummer vergibt der
Nummernkreis bei der Festschreibung und ist je Anlage eine andere.

`betrag` darf an der Zahlung und an jeder Zuordnung fehlen; dann wird die
Rechnung vollständig ausgeglichen und die Zahlung ist die Summe daraus. Wer
eine **Teilzahlung** zeigen will, nennt beide Beträge; wer eine
**unverteilte Zahlung** zeigen will, nennt am Kopf mehr, als die Zuordnungen
zusammen ergeben. `skonto` an einer Zuordnung gleicht zusätzlich aus, ohne
dass Geld geflossen ist.

Eine Rechnung, die hier nicht genannt ist, bleibt offen, und ein paar
offene gehören dazu.

**Ausnahme: Abschläge eines Vorhabens mit Schlussrechnung.** Deren Zahlung
steht am Abschlag selbst, als `"bezahlt_vor_tagen": 131` in der
Projektdatei, und wird gleich nach dem Abschlag gebucht. Die
Schlussrechnung setzt nur ab, was zu dem Zeitpunkt bezahlt ist, und fordert
den Rest selbst; eine Zahlung aus dieser Datei käme zu spät und stünde
doppelt da.

**Die Standard-Textbausteine stehen nicht im Bestand.** Anrede,
Grußformel, die Einleitungen je Belegart und die Mail-Anschreiben gehören
zur Grundausstattung jeder Anlage und liegen deshalb in `paper-werk-app`
(`faktura/standardtexte.py`). Der Lader legt sie mit dem Betrieb an und
setzt dabei den Firmennamen in die Grußformel. In `NN-textbausteine.json`
steht nur, was ein Gewerk darüber hinaus hat. Ein Name, den es schon gibt,
bricht den Lauf ab, damit kein Standardtext still überschrieben wird.
Ein Eintrag hat `name` und `text`, dazu optional `verwendung` (`belegtext`,
die Vorgabe, oder `mail`) und `belegart` (leer heißt: jede).

Eine Art, die nicht gebraucht wird, lässt man weg. Eine Datei mit einem
unbekannten Namen ist ein Fehler, damit ein Tippfehler wie
`kundne.json` nicht still einen Bestand auslässt.

## Fünf Regeln, mehr sind es nicht

**1. Verwiesen wird über Namen, nie über Positionen.** Ein Kleinauftrag
nennt seinen Kunden beim Namen (`"kunde": "Hausverwaltung Brunner"`), eine
Position ihre Leistung (`"leistung": "Meisterstunde"`). Steht der Name
nirgends, bricht der Lauf ab und sagt, welche Namen er kennt. Indizes wie
`kunde: 4` gibt es nicht, weil die nach sechs Monaten niemand mehr versteht.

**2. Datumsangaben sind relativ zu heute**, in Tagen oder Monaten:
`"vor_tagen": 132`, `"vor_monaten": 11`. Ein fest eingetragenes Jahr sähe
schon im Januar alt aus. Für Projektnummern gibt es den Platzhalter
`{jahr}`, der zum laufenden Jahr wird.

Die **einzige Ausnahme** sind `leistung_von_tagen` und
`leistung_bis_tagen` an einem Beleg: Die zählen **ab dem Belegdatum**
zurück, nicht ab heute. Deshalb heißen sie auch anders. Fachlich ist das
der einzig sinnvolle Bezug: Die Leistung liegt ein paar Tage vor der
Rechnung, egal wann die geschrieben wurde. Ohne Angabe bekommt der Beleg
einen Leistungstag 30 Tage vor sich selbst; Angebot, Auftrag und Nachtrag
dagegen einen geplanten Beginn eine Woche **nach** sich selbst.

**3. Am Wochenende wird nicht gebucht.** Der Lader lässt Samstag und Sonntag
still weg, weil ein Bestand, in dem durchgearbeitet wird, jedem Praktiker
sofort auffällt. Daraus folgt eine Falle: Eine Tagesliste im Sieben-Tage-Schritt
(`[80, 73, 66, 59]`) liegt komplett auf **einem** Wochentag, und je nach Tag
des Laufs verschwindet sie vollständig. Tage deshalb ungleichmäßig streuen.

Und: **Eine Person ist nicht an zwei Orten zugleich.** Überschneiden sich
zwei Zeilen derselben Person am selben Tag (auch über Vorhaben hinweg),
bricht der Lauf ab. Wer eine Person auf mehrere Vorhaben bucht, legt die
Tage oder die Uhrzeiten auseinander.

**4. Jedes Feld, das mit `_` beginnt, ist ein Kommentar** und wird
weggeworfen; `_kommentar` steht überall dort, wo die Erklärung hingehört, auch an
einer einzelnen Position. Dieselbe Konvention wie in den
Paperless-Starterpaketen.

**5. Beträge stehen als Text in Anführungszeichen** (`"78.00"`), nicht als
Zahl. Mengen und Tage dürfen Zahlen sein. Der Grund ist Geld: `78.10` ist
als Fließkommazahl nicht genau 78,10, und in einer Rechnung fällt das
irgendwann auf.

## Wenn etwas nicht geht

Der Lader bricht ab und nimmt alles zurück; es bleibt nichts Halbes stehen.
Die Meldung sagt, was fehlte, und bei Namen auch, welche er kennt.

Was er sonst **nicht** tut: prüfen, ob der Bestand fachlich sinnvoll ist.
Ein Projekt mit 300 Prozent Ausschöpfung läuft anstandslos durch. Ob die Zahlen
eine Geschichte erzählen, die man vorführen kann, entscheidet der, der den
Bestand schreibt.
