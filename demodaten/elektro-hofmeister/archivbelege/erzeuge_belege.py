"""Erzeugt die Papierbelege in diesem Ordner neu.

**Kein Teil der Anwendung**: ein Werkzeug, das man selten braucht. Es steht
hier aus demselben Grund wie ``beispiele/e-rechnung/erzeuge_pdf.py``: Die
PDF-Dateien daneben sind die einzigen im Repo, die man nicht lesen und nicht
von Hand reparieren kann. Ohne das Skript wäre nicht nachvollziehbar, wie
sie entstanden sind.

**Wozu diese Belege da sind.** Der Demobestand ``elektro-hofmeister``
erzeugt nur AUSGANGSbelege: Angebote, Rechnungen, Mahnungen, die beim
Festschreiben ins Archiv wandern. Ein Archiv zeigt sich aber erst an dem,
was hereinkommt: Tankquittung, Mietvertrag, Bescheid, Lieferschein.

Sie decken zugleich die Dokumenttypen ab, die das Starterpaket ``elektro``
mitbringt (Prüfprotokoll, Netzanmeldung, Abnahmeprotokoll). Sonst stünden
die Typen leer da und niemand wüsste, wofür sie gedacht sind.

**Feste Datumsangaben und nicht relativ zu heute**, anders als im Seed. Der
Grund ist die Reproduzierbarkeit: Ein Skript, das bei jedem Lauf andere
Dateien schreibt, macht aus jedem Lauf eine Änderung im Repo, und die
Frage "ist das noch dieselbe Datei" lässt sich dann nicht mehr beantworten.
Die Belege liegen im Sommer 2026 und passen damit zum Bestand, der auf
denselben Zeitraum gerechnet ist.

**Byte-genau wiederholbar, und das ist nicht selbstverständlich.** Beim
ersten Lauf ergaben zwei Durchgänge hintereinander sieben verschiedene
Dateien: WeasyPrint stempelt Erzeugungs- und Änderungszeit ins PDF. Der
Inhalt war jedesmal derselbe, die Datei nicht, und damit hätte jeder Lauf
eine Änderung im Repo erzeugt, ohne dass sich etwas geändert hätte.

Gelöst über ``SOURCE_DATE_EPOCH``, die Übereinkunft der reproducible
builds: WeasyPrint nimmt den Wert als Erzeugungszeit, wenn er gesetzt ist.
Das Skript setzt ihn selbst (siehe ``ZEITSTEMPEL``), damit niemand daran
denken muss; zwei Läufe ergeben dieselben Prüfsummen.

Aufruf aus dem Wurzelverzeichnis des Projekts::

    uv run --project ../paper-werk-app python \
    demodaten/elektro-hofmeister/archivbelege/erzeuge_belege.py

Braucht GTK (für WeasyPrint), siehe die Erklärung in ``faktura/pdf.py``.
"""

import os
import sys
from pathlib import Path

import django

BASIS = Path(__file__).resolve().parent

#: Die Erzeugungszeit, die in jedem dieser PDF steht: 01.09.2026, 12:00 UTC.
#
# **Vor dem Import von WeasyPrint gesetzt**, nicht später: Die Bibliothek
# liest die Variable, wenn sie das Dokument schreibt, und ein später
# gesetzter Wert käme zu spät. Der Wert selbst ist beliebig, aber fest -
# er ist ein technisches Metadatum und steht auf keinem Beleg.
#
# ``setdefault`` und nicht ``=``: Wer von aussen einen anderen Wert setzt
# (etwa ein Build, der alle Artefakte auf denselben Stempel bringt), soll
# ihn behalten.
ZEITSTEMPEL = '1788264000'
os.environ.setdefault('SOURCE_DATE_EPOCH', ZEITSTEMPEL)

sys.path.insert(0, str(BASIS.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperwerk.settings.dev')
django.setup()

from faktura import pdf as faktura_pdf  # noqa: E402

#: Der gemeinsame Satz; jeder Beleg setzt nur seinen Inhalt darauf.
#
# Bewusst schlicht und nicht nachgebaut: Diese Belege sollen nach Papier
# aussehen, das jemand eingescannt hat, nicht nach einem Musterbrief. Was
# zählt, ist der Text: Paperless liest ihn, die Arbeitsabläufe greifen
# darauf, und im Termin wird danach gesucht.
STIL = """
<style>
  @page { size: A4; margin: 24mm 22mm; }
  body { font-family: "Segoe UI", sans-serif; font-size: 10.5pt; color: #111; }
  .absender { font-size: 8pt; color: #555; border-bottom: .5pt solid #bbb;
              padding-bottom: 2mm; margin-bottom: 12mm; }
  h1 { font-size: 16pt; margin: 0 0 2mm 0; }
  .betreff { font-weight: 600; margin: 10mm 0 5mm 0; }
  .kopf { display: flex; justify-content: space-between; margin-bottom: 8mm; }
  .kopf dl { margin: 0; font-size: 9pt; }
  .kopf dt { color: #666; }
  .kopf dd { margin: 0 0 1.5mm 0; }
  .empfaenger { font-size: 10pt; line-height: 1.5; margin-top: 6mm; }
  table { width: 100%; border-collapse: collapse; margin: 5mm 0; }
  th { text-align: left; font-size: 8pt; text-transform: uppercase;
       letter-spacing: .04em; color: #666; border-bottom: .8pt solid #333;
       padding-bottom: 1.5mm; }
  td { padding: 2mm 0; border-bottom: .3pt solid #ddd;
       font-variant-numeric: tabular-nums; }
  .r { text-align: right; }
  .summe { font-weight: 600; border-top: .8pt solid #333; }
  p { line-height: 1.55; }
  .fuss { margin-top: 14mm; font-size: 8pt; color: #666;
          border-top: .5pt solid #bbb; padding-top: 3mm; }
  .hinweis { margin-top: 10mm; font-size: 8pt; color: #444;
             background: #f4f4f2; padding: 3mm 4mm; }
</style>
"""

#: Der Empfänger, immer derselbe Betrieb wie im Vorführbestand.
#
# Zeichengenau wie in ``05-lieferanten.json``: Paperless erkennt
# Korrespondenten über den Namen, und ein "Elektro Hofmeister e.K." neben
# einem "Elektro Hofmeister eK" wären zwei.
EMPFAENGER = ('Elektro Hofmeister e.K.<br>'
              'Schirmbeckstra&szlig;e 14<br>'
              '84034 Landshut')

#: Der Hinweis, der auf jedem dieser Belege steht.
#
# **Nicht verhandelbar**: Diese Dateien sehen aus wie echte Belege und
# liegen in einem Archiv neben echten. Ohne die Kennzeichnung wäre der Tag
# absehbar, an dem eine davon in einer Buchhaltung landet. Der Test
# ``test_jeder_beleg_ist_als_beispiel_gekennzeichnet`` hält das fest.
KENNZEICHNUNG = (
    '<div class="hinweis">Beispieldatei aus dem Vorf&uuml;hrbestand von '
    'paper-werk. Erfundener Beleg &ndash; kein Zahlungsbeleg, keine '
    'Buchungsgrundlage.</div>'
)


def _seite(titel, absender, kopf, inhalt, fuss=''):
    """Setzt einen Beleg aus den immer gleichen Teilen zusammen."""
    zeilen = ''.join(
        f'<dt>{bez}</dt><dd>{wert}</dd>' for bez, wert in kopf)
    return (
        f'{STIL}'
        f'<div class="absender">{absender}</div>'
        f'<div class="kopf">'
        f'  <div><h1>{titel}</h1>'
        f'    <div class="empfaenger">{EMPFAENGER}</div></div>'
        f'  <dl>{zeilen}</dl>'
        f'</div>'
        f'{inhalt}'
        f'{f"<div class=\'fuss\'>{fuss}</div>" if fuss else ""}'
        f'{KENNZEICHNUNG}'
    )


BELEGE = {}

# ── Der Kleinbeleg, den jeder kennt ──────────────────────────────────────────
BELEGE['tankquittung-2026-08-19.pdf'] = _seite(
    'Quittung',
    'Autohof Ergolding &middot; Landshuter Stra&szlig;e 88 &middot; '
    '84030 Ergolding',
    [('Beleg-Nr.', '4471-08832'), ('Datum', '19.08.2026'),
     ('Uhrzeit', '07:14'), ('Zapfs&auml;ule', '3')],
    '<table><thead><tr><th>Artikel</th><th class="r">Menge</th>'
    '<th class="r">Preis</th><th class="r">Betrag</th></tr></thead>'
    '<tbody>'
    '<tr><td>Diesel</td><td class="r">62,41 l</td>'
    '<td class="r">1,689 &euro;/l</td><td class="r">105,41 &euro;</td></tr>'
    '<tr><td>Scheibenreiniger</td><td class="r">1 Stk</td>'
    '<td class="r">4,99 &euro;</td><td class="r">4,99 &euro;</td></tr>'
    '</tbody><tfoot>'
    '<tr class="summe"><td colspan="3">Summe brutto</td>'
    '<td class="r">110,40 &euro;</td></tr>'
    '<tr><td colspan="3">darin 19 % USt</td>'
    '<td class="r">17,63 &euro;</td></tr>'
    '</tfoot></table>'
    '<p style="font-size:9pt">Kennzeichen LA-EH 214 &middot; '
    'Kilometerstand 84.117</p>',
    'Autohof Ergolding GmbH &middot; USt-IdNr. DE224180933')

# ── Der Vertrag, der Jahre trägt ────────────────────────────────────────────
BELEGE['mietvertrag-werkstatt.pdf'] = _seite(
    'Mietvertrag &uuml;ber Gewerber&auml;ume',
    'Hausverwaltung Brunnhuber &middot; Ludwigstra&szlig;e 40 &middot; '
    '84034 Landshut',
    [('Vertrags-Nr.', 'GV-2025-114'), ('Abgeschlossen am', '18.11.2025'),
     ('Mietbeginn', '01.01.2026'), ('Laufzeit', '5 Jahre')],
    '<p class="betreff">Werkstatt und Lager, Schirmbeckstra&szlig;e 14, '
    '84034 Landshut</p>'
    '<p><b>&sect; 1 Mietgegenstand.</b> Vermietet werden eine Werkstatthalle '
    'von 214 m&sup2; sowie ein Lagerraum von 38 m&sup2; nebst zwei '
    'Stellpl&auml;tzen im Hof. Die R&auml;ume sind zum Betrieb eines '
    'Elektrofachbetriebs bestimmt.</p>'
    '<p><b>&sect; 2 Mietzins.</b> Die Grundmiete betr&auml;gt monatlich '
    '1.480,00 &euro; zuz&uuml;glich 320,00 &euro; Nebenkostenvorauszahlung, '
    'insgesamt 1.800,00 &euro;. Der Betrag ist bis zum dritten Werktag eines '
    'Monats im Voraus zu zahlen.</p>'
    '<p><b>&sect; 3 Laufzeit und K&uuml;ndigung.</b> Das Mietverh&auml;ltnis '
    'beginnt am 01.01.2026 und l&auml;uft f&uuml;nf Jahre fest. Es '
    'verl&auml;ngert sich um jeweils zwei Jahre, wenn es nicht sp&auml;testens '
    'sechs Monate vor Ablauf schriftlich gek&uuml;ndigt wird.</p>'
    '<p><b>&sect; 4 Instandhaltung.</b> Sch&ouml;nheitsreparaturen im Inneren '
    'obliegen dem Mieter. Die elektrische Anlage des Geb&auml;udes bleibt '
    'Sache des Vermieters; abweichend hiervon &uuml;bernimmt der Mieter die '
    'wiederkehrende Pr&uuml;fung nach DGUV Vorschrift 3 auf eigene '
    'Rechnung.</p>',
    'Hausverwaltung Brunnhuber e.K. &middot; Landshut')

# ── Die Versicherung, die einmal im Jahr schreibt ────────────────────────────
BELEGE['versicherung-betriebshaftpflicht-2026.pdf'] = _seite(
    'Versicherungsschein',
    'Bayerische Handwerksversicherung AG &middot; Karolinenplatz 6 '
    '&middot; 80333 M&uuml;nchen',
    [('Versicherungsschein-Nr.', 'BHV-8841-2026'),
     ('Ausgestellt am', '12.01.2026'),
     ('Versicherungsjahr', '01.01.2026 &ndash; 31.12.2026'),
     ('Beitrag j&auml;hrlich', '1.284,00 &euro;')],
    '<p class="betreff">Betriebshaftpflichtversicherung f&uuml;r das '
    'Elektrohandwerk</p>'
    '<table><thead><tr><th>Deckung</th><th class="r">Summe</th></tr></thead>'
    '<tbody>'
    '<tr><td>Personen- und Sachsch&auml;den, pauschal</td>'
    '<td class="r">5.000.000 &euro;</td></tr>'
    '<tr><td>Verm&ouml;genssch&auml;den</td><td class="r">250.000 &euro;</td></tr>'
    '<tr><td>T&auml;tigkeitssch&auml;den an bearbeiteten Sachen</td>'
    '<td class="r">250.000 &euro;</td></tr>'
    '<tr><td>Sch&auml;den durch Elektroinstallationsarbeiten</td>'
    '<td class="r">eingeschlossen</td></tr>'
    '</tbody></table>'
    '<p>Mitversichert sind die Inbetriebnahme und Wartung von '
    'Ladeeinrichtungen f&uuml;r Elektrofahrzeuge sowie Arbeiten an '
    'Photovoltaikanlagen bis 30 kWp. Die Selbstbeteiligung betr&auml;gt '
    '500,00 &euro; je Schadenfall.</p>'
    '<p><b>Beitragsf&auml;lligkeit:</b> j&auml;hrlich zum 01.02., erstmals '
    'am 01.02.2026.</p>',
    'Bayerische Handwerksversicherung AG &middot; Amtsgericht M&uuml;nchen HRB 44218')

# ── Der Bescheid mit Frist ───────────────────────────────────────────────────
BELEGE['hwk-beitragsbescheid-2026.pdf'] = _seite(
    'Beitragsbescheid',
    'Handwerkskammer Niederbayern-Oberpfalz &middot; '
    'Ditthornstra&szlig;e 10 &middot; 93055 Regensburg',
    [('Betriebs-Nr.', 'HWK-84-021477'), ('Bescheiddatum', '04.02.2026'),
     ('Beitragsjahr', '2026'), ('F&auml;llig am', '15.03.2026')],
    '<p class="betreff">Beitrag zur Handwerkskammer f&uuml;r das Jahr 2026</p>'
    '<table><thead><tr><th>Position</th><th class="r">Betrag</th></tr></thead>'
    '<tbody>'
    '<tr><td>Grundbeitrag (Einzelunternehmen)</td>'
    '<td class="r">196,00 &euro;</td></tr>'
    '<tr><td>Zusatzbeitrag, 0,18 % des Gewerbeertrags 2024</td>'
    '<td class="r">142,60 &euro;</td></tr>'
    '<tr><td>Umlage Berufsbildung</td><td class="r">64,00 &euro;</td></tr>'
    '</tbody><tfoot>'
    '<tr class="summe"><td>Gesamtbetrag</td>'
    '<td class="r">402,60 &euro;</td></tr>'
    '</tfoot></table>'
    '<p><b>Rechtsbehelfsbelehrung.</b> Gegen diesen Bescheid kann innerhalb '
    'eines Monats nach Bekanntgabe Widerspruch erhoben werden. Der '
    'Widerspruch ist schriftlich oder zur Niederschrift bei der '
    'Handwerkskammer Niederbayern-Oberpfalz einzulegen.</p>',
    'Handwerkskammer Niederbayern-Oberpfalz &middot; K&ouml;rperschaft des '
    '&ouml;ffentlichen Rechts')

# ── Der Lieferschein zur Rechnung, die es schon gibt ─────────────────────────
BELEGE['lieferschein-wittmann-880366.pdf'] = _seite(
    'Lieferschein',
    'Elektro-Gro&szlig;handel Wittmann KG &middot; Gewerbepark S&uuml;d 14 '
    '&middot; 84030 Ergolding',
    [('Lieferschein-Nr.', 'LS-88-24103'), ('Datum', '20.08.2026'),
     ('Ihre Kundennummer', '41-8802'),
     ('Rechnung', 'WI-880366')],
    '<p class="betreff">Materiallieferung Baustelle Ludwigsplatz 9</p>'
    '<table><thead><tr><th>Pos.</th><th>Artikel</th>'
    '<th class="r">Menge</th><th>Einheit</th></tr></thead>'
    '<tbody>'
    '<tr><td>1</td><td>Mantelleitung NYM-J 3x1,5 mm&sup2;, Ring 100 m</td>'
    '<td class="r">400</td><td>m</td></tr>'
    '<tr><td>2</td><td>FI/LS-Schalter 16 A / 30 mA, Typ A</td>'
    '<td class="r">12</td><td>Stk</td></tr>'
    '<tr><td>3</td><td>Schutzkontakt-Steckdose UP, reinwei&szlig;</td>'
    '<td class="r">40</td><td>Stk</td></tr>'
    '<tr><td>4</td><td>Installationskleinmaterial (Dosen, Klemmen, Schellen)</td>'
    '<td class="r">1</td><td>Pos</td></tr>'
    '</tbody></table>'
    '<p style="font-size:9pt">Ware vollst&auml;ndig und unbesch&auml;digt '
    '&uuml;bernommen. Die Berechnung erfolgt mit Rechnung WI-880366.</p>',
    'Elektro-Gro&szlig;handel Wittmann KG &middot; USt-IdNr. DE298114736')

# ── Der Beleg, der das Gewerk ausmacht ───────────────────────────────────────
BELEGE['pruefprotokoll-dguv-v3-bauhof.pdf'] = _seite(
    'Pr&uuml;fprotokoll',
    'Elektro Hofmeister e.K. &middot; Schirmbeckstra&szlig;e 14 &middot; '
    '84034 Landshut',
    [('Protokoll-Nr.', 'PR-2026-0114'), ('Pr&uuml;fdatum', '09.07.2026'),
     ('N&auml;chste Pr&uuml;fung', '09.07.2027'),
     ('Pr&uuml;fer', 'M. Hofmeister, Elektromeister')],
    '<p class="betreff">Wiederholungspr&uuml;fung ortsver&auml;nderlicher '
    'Betriebsmittel nach DGUV Vorschrift 3 / DIN VDE 0701-0702</p>'
    '<p><b>Auftraggeber:</b> Gemeinde Altdorf, Rathausplatz 1, '
    '84032 Altdorf &middot; <b>Pr&uuml;fort:</b> Bauhof, '
    'Rottenburger Stra&szlig;e 12</p>'
    '<table><thead><tr><th>Ger&auml;t</th><th>Inventar-Nr.</th>'
    '<th class="r">Schutzleiter</th><th class="r">Isolation</th>'
    '<th>Ergebnis</th></tr></thead>'
    '<tbody>'
    '<tr><td>Handbohrmaschine</td><td>BH-0214</td><td class="r">0,12 &Omega;</td>'
    '<td class="r">&gt; 300 M&Omega;</td><td>bestanden</td></tr>'
    '<tr><td>Winkelschleifer</td><td>BH-0218</td><td class="r">0,09 &Omega;</td>'
    '<td class="r">&gt; 300 M&Omega;</td><td>bestanden</td></tr>'
    '<tr><td>Verl&auml;ngerungsleitung 25 m</td><td>BH-0231</td>'
    '<td class="r">0,41 &Omega;</td><td class="r">2,1 M&Omega;</td>'
    '<td><b>Mangel</b></td></tr>'
    '<tr><td>Kreiss&auml;ge</td><td>BH-0244</td><td class="r">0,14 &Omega;</td>'
    '<td class="r">&gt; 300 M&Omega;</td><td>bestanden</td></tr>'
    '</tbody></table>'
    '<p><b>Feststellung.</b> Von 218 gepr&uuml;ften Betriebsmitteln haben '
    '214 bestanden. Vier Ger&auml;te weisen M&auml;ngel auf und wurden der '
    'Nutzung entzogen; die Verl&auml;ngerungsleitung BH-0231 '
    'unterschreitet den Isolationswiderstand. Eine Nachpr&uuml;fung nach '
    'Instandsetzung ist erforderlich.</p>',
    'Erstellt nach DIN VDE 0701-0702 &middot; Pr&uuml;fplaketten angebracht')

# ── Der Beleg, ohne den keine Wallbox läuft ─────────────────────────────────
BELEGE['netzanmeldung-wallbox-autohaus.pdf'] = _seite(
    'Inbetriebsetzungsanzeige',
    'Bayernwerk Netz &ndash; Netzbetreiber &middot; '
    'Lilienthalstra&szlig;e 7 &middot; 93049 Regensburg',
    [('Vorgangs-Nr.', 'IBS-2026-114772'), ('Eingegangen am', '14.07.2026'),
     ('Best&auml;tigt am', '29.07.2026'),
     ('Z&auml;hlernummer', '1EBZ0100874412')],
    '<p class="betreff">Anmeldung von Ladeeinrichtungen nach &sect; 19 NAV</p>'
    '<p><b>Anlagenbetreiber:</b> Autohaus Brandmeier GmbH, Am Nordring 3, '
    '84032 Landshut &middot; <b>Errichter:</b> Elektro Hofmeister e.K. '
    '(eingetragen im Installateurverzeichnis, Nr. 84-4471)</p>'
    '<table><thead><tr><th>Ladepunkt</th><th>Seriennummer</th>'
    '<th class="r">Leistung</th><th>Status</th></tr></thead>'
    '<tbody>'
    '<tr><td>Stellplatz 1</td><td>WB-11-2026-40871</td>'
    '<td class="r">11 kW</td><td>zugestimmt</td></tr>'
    '<tr><td>Stellplatz 2</td><td>WB-11-2026-40872</td>'
    '<td class="r">11 kW</td><td>zugestimmt</td></tr>'
    '<tr><td>Stellplatz 3 bis 6</td><td>Nachmeldung</td>'
    '<td class="r">44 kW</td><td>in Pr&uuml;fung</td></tr>'
    '</tbody></table>'
    '<p>Die Gesamtanschlussleistung von 66 kW &uuml;berschreitet die '
    'zustimmungsfreie Grenze von 12 kVA. F&uuml;r die Ladepunkte 3 bis 6 ist '
    'ein Nachweis des Lastmanagements vorzulegen; bis dahin ruht die '
    'Zustimmung f&uuml;r diesen Teil der Anlage.</p>',
    'Bayernwerk Netz &middot; Anschluss- und Inbetriebsetzungswesen')


def main():
    BASIS.mkdir(parents=True, exist_ok=True)
    for name, html in BELEGE.items():
        ziel = BASIS / name
        # Derselbe Aufruf wie in beispiele/e-rechnung/erzeuge_pdf.py und
        # wie für die eigenen Rechnungen: PDF/A-3b, damit die Dateien
        # archivtauglich sind wie alles andere im Bestand auch.
        ziel.write_bytes(
            faktura_pdf.weasyprint.HTML(string=html).write_pdf(
                pdf_variant='pdf/a-3b'))
        print(f'  {name}  ({ziel.stat().st_size // 1024} kB)')
    print(f'\n{len(BELEGE)} Belege geschrieben nach {BASIS}')


if __name__ == '__main__':
    main()
