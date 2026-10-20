"""Erzeugt die Eingangsrechnungen in diesem Ordner neu.

**Kein Teil der Anwendung**: ein Werkzeug für den Demobestand, wie
``archivbelege/erzeuge_belege.py``. Die PDF-Dateien daneben kann man nicht
lesen und nicht von Hand reparieren; ohne dieses Skript wäre nicht
nachvollziehbar, wie sie entstanden sind.

**Wozu.** Der Belegweg "Rechnung aus Paperless nach paper-werk" braucht
Rechnungen, die an Elektro Hofmeister gehen, und zwar beide Sorten:
E-Rechnungen (PDF mit eingebettetem XML, ZUGFeRD/Factur-X), bei denen
paper-werk alles selbst liest, und gewöhnliche PDF, bei denen Mistral den
Text liest. Jede Rechnung zeigt eine andere Wendung, siehe ``RECHNUNGEN``
und die README.

**Dieselbe Kette wie die eigenen Rechnungen der App**: WeasyPrint setzt
die Seite als PDF/A-3b, ``drafthorse`` hängt das XML an. Das XML wird hier
aus einer Vorlage gebaut und vor dem Schreiben mit dem Leser der App
gegengelesen (``erfassung.erechnung.lesen``), weil eine Datei, die paper-werk
selbst nicht liest, für die Vorführung wertlos wäre.

Aufruf aus dem Wurzelverzeichnis von paper-werk-app::

    uv run python ../paper-werk/demodaten/elektro-hofmeister/eingangsrechnungen/erzeuge_rechnungen.py

Braucht GTK (für WeasyPrint), siehe die Erklärung in ``faktura/pdf.py``.
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import django

BASIS = Path(__file__).resolve().parent
APP = BASIS.parents[3] / 'paper-werk-app'

#: Erzeugungszeit in den PDF-Metadaten, fest wie in archivbelege.
os.environ.setdefault('SOURCE_DATE_EPOCH', '1790856000')

sys.path.insert(0, str(APP))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperwerk.settings.dev')
django.setup()

# Nach django.setup(): faktura.pdf meldet beim Import das GTK-Verzeichnis an.
from drafthorse.pdf import attach_xml  # noqa: E402

from erfassung import erechnung  # noqa: E402
from faktura import pdf as faktura_pdf  # noqa: E402

CENT = Decimal('0.01')
UST = Decimal('19')

#: Der Empfänger, zeichengenau wie im Vorführbestand (01-betrieb.json).
KAEUFER = {
    'name': 'Elektro Hofmeister e.K.',
    'strasse': 'Schirmbeckstraße 14',
    'plz': '84034',
    'ort': 'Landshut',
}

#: Einheit auf der Seite -> Code nach UN/ECE Rec. 20 im XML.
EINHEIT_CODE = {'Stk': 'C62', 'm': 'MTR', 'Std': 'HUR', 'Tag': 'DAY',
                'psch': 'C62', 'm²': 'MTK'}


@dataclass
class Lieferant:
    name: str
    strasse: str
    plz: str
    ort: str
    ust_id: str
    iban: str
    bank: str


@dataclass
class Rechnung:
    datei: str
    lieferant: Lieferant
    nummer: str
    datum: date
    leistung: date
    faellig: date
    positionen: list  # (Bezeichnung, Menge, Einheit, Einzelpreis)
    erechnung: bool
    betreff: str
    #: BT-11; steht in der XML nur, wenn gesetzt, auf der Seite immer.
    projektreferenz: str = ''
    bestellung: str = ''
    #: Was die Seite zusätzlich zeigt, für Mistral und für die Vorführung.
    zeilen_kopf: list = field(default_factory=list)

    @property
    def netto(self) -> Decimal:
        return sum((zeile_betrag(p) for p in self.positionen), Decimal('0'))

    @property
    def steuer(self) -> Decimal:
        return (self.netto * UST / 100).quantize(CENT, ROUND_HALF_UP)

    @property
    def brutto(self) -> Decimal:
        return self.netto + self.steuer


def zeile_betrag(position) -> Decimal:
    _, menge, _, preis = position
    return (Decimal(menge) * Decimal(preis)).quantize(CENT, ROUND_HALF_UP)


# ══════════════════════════════════════════════════════════════════════════
# Die Lieferanten
#
# Wittmann und Ladetechnik zeichengenau wie in 05-lieferanten.json und den
# Beispiel-XML der App, sonst legt das Einlesen einen zweiten Lieferanten
# an. Der PV-Großhandel ist absichtlich NEU: An ihm sieht man, dass
# paper-werk einen unbekannten Lieferanten anlegt und kennzeichnet.
# ══════════════════════════════════════════════════════════════════════════

WITTMANN = Lieferant(
    'Elektro-Großhandel Wittmann KG', 'Gewerbepark Süd 14', '84030',
    'Ergolding', 'DE298114736', 'DE44743500000002881904',
    'Sparkasse Landshut')
LADETECHNIK = Lieferant(
    'Ladetechnik Süd GmbH', 'Am Fliegerhorst 8', '85356', 'Freising',
    'DE331470268', 'DE19700202700016558741', 'HypoVereinsbank Freising')
PV_ISAR = Lieferant(
    'Solar-Großhandel Isar GmbH', 'Industriestraße 22', '84130',
    'Dingolfing', 'DE341207755', 'DE62743200730023418806',
    'VR-Bank Landau-Mengkofen')
ZELLNER = Lieferant(
    'Gerüstbau Zellner', 'Moosstraße 3', '84051', 'Essenbach',
    'DE287003164', 'DE88743500000020731155', 'Sparkasse Landshut')


RECHNUNGEN = [
    # 1. Der Regelfall der E-Rechnung: Die Projektreferenz trifft ein
    #    laufendes Projekt, paper-werk füllt auch die Projektnummer, der
    #    Mensch muss nur noch "Paper-Werk senden" setzen.
    Rechnung(
        datei='wittmann-881477-e-rechnung.pdf',
        lieferant=WITTMANN, nummer='WI-881477',
        datum=date(2026, 9, 22), leistung=date(2026, 9, 19),
        faellig=date(2026, 10, 22), erechnung=True,
        betreff='Material Elektrosanierung Ludwigsplatz 9',
        projektreferenz='BV Ludwigsplatz 9, Projekt 2026-014',
        bestellung='EH-2026-0412',
        positionen=[
            ('NYM-J 3x1,5 mm², Ring 100 m', '6', 'Stk', '64.80'),
            ('NYM-J 5x2,5 mm², Ring 50 m', '2', 'Stk', '98.40'),
            ('Unterverteiler 4-reihig, 48 TE, UP', '3', 'Stk', '142.90'),
            ('FI/LS-Schalter B16 30 mA', '18', 'Stk', '38.75'),
            ('Schalterprogramm reinweiß, Steckdose', '64', 'Stk', '4.95'),
        ]),

    # 2. E-Rechnung OHNE Projektreferenz: Die Felder kommen aus dem XML,
    #    nur die Projektnummer bleibt leer. Der Mensch trägt 2026-021 ein -
    #    die Bestellung auf der Seite sagt ihm, wohin es gehört.
    Rechnung(
        datei='ladetechnik-3521-e-rechnung.pdf',
        lieferant=LADETECHNIK, nummer='LS-2026-3521',
        datum=date(2026, 9, 24), leistung=date(2026, 9, 23),
        faellig=date(2026, 10, 8), erechnung=True,
        betreff='Lastmanagement und Montagezubehör',
        bestellung='Autohaus Brandmeier, Ladepunkte 7-12',
        positionen=[
            ('Lastmanagement-Controller für 12 Ladepunkte', '1', 'Stk',
             '1180.00'),
            ('Standsäule für Wallbox, verzinkt', '6', 'Stk', '214.00'),
            ('Energiezähler MID, 3-phasig', '6', 'Stk', '96.50'),
            ('Inbetriebnahme Lastmanagement vor Ort', '3.5', 'Std', '95.00'),
        ]),

    # 3. E-Rechnung von einem Lieferanten, den paper-werk noch nicht kennt:
    #    Er wird angelegt und mit einem Vermerk gekennzeichnet.
    Rechnung(
        datei='solar-isar-26-1093-e-rechnung.pdf',
        lieferant=PV_ISAR, nummer='SI-26-1093',
        datum=date(2026, 9, 25), leistung=date(2026, 9, 25),
        faellig=date(2026, 10, 9), erechnung=True,
        betreff='Wechselrichter und Speicher PV Schreinerei Gruber',
        projektreferenz='2026-031',
        positionen=[
            ('Hybrid-Wechselrichter 10 kW', '1', 'Stk', '1890.00'),
            ('Batteriespeicher 10,2 kWh, modular', '1', 'Stk', '4260.00'),
            ('Smart Meter, 3-phasig', '1', 'Stk', '185.00'),
            ('Solarkabel 6 mm², rot/schwarz', '100', 'm', '1.28'),
        ]),

    # 4. Gewöhnliches PDF: kein XML, Mistral liest den Text. Das
    #    Bauvorhaben steht so auf der Seite, wie ein Gerüstbauer es schreibt.
    Rechnung(
        datei='zellner-2026-117.pdf',
        lieferant=ZELLNER, nummer='2026-117',
        datum=date(2026, 9, 26), leistung=date(2026, 9, 12),
        faellig=date(2026, 10, 10), erechnung=False,
        betreff='Gerüststellung Neubau Einfamilienhaus Steinberger',
        projektreferenz='Ihr Projekt 2026-028, Neubau EFH Steinberger',
        positionen=[
            ('Fassadengerüst auf- und abbauen', '186', 'm²', '7.40'),
            ('Standzeit über 4 Wochen hinaus, je Woche', '2', 'Stk',
             '112.00'),
            ('An- und Abfahrt', '1', 'psch', '95.00'),
        ]),

    # 5. Gewöhnliches PDF ohne Projekt: Lagermaterial. Die Rechnung kommt
    #    unkontiert an, ihr Betrag steht in paper-werk als offener Rest -
    #    sichtbar, bis jemand sie verteilt.
    Rechnung(
        datei='wittmann-881502.pdf',
        lieferant=WITTMANN, nummer='WI-881502',
        datum=date(2026, 9, 29), leistung=date(2026, 9, 29),
        faellig=date(2026, 10, 29), erechnung=False,
        betreff='Lagerauffüllung Kleinmaterial',
        positionen=[
            ('Wago-Klemmen 221-413, 50er Pack', '8', 'Stk', '14.90'),
            ('Kabelbinder 4,8x200 mm, 100er Pack', '10', 'Stk', '3.60'),
            ('Isolierband sortiert, 10er Pack', '4', 'Stk', '7.80'),
            ('Schraubensortiment Elektro', '2', 'Stk', '24.50'),
        ]),
]


# ══════════════════════════════════════════════════════════════════════════
# Die Seite
# ══════════════════════════════════════════════════════════════════════════

STIL = """
<style>
  @page { size: A4; margin: 22mm 20mm; }
  body { font-family: "Segoe UI", sans-serif; font-size: 10pt; color: #111; }
  .absender { font-size: 7.5pt; color: #666; border-bottom: .5pt solid #bbb;
              padding-bottom: 2mm; margin-bottom: 14mm; }
  .firma { font-size: 13pt; font-weight: 600; margin-bottom: 2mm; }
  h1 { font-size: 15pt; margin: 0 0 1mm 0; }
  .kopf { display: flex; justify-content: space-between; margin-bottom: 10mm; }
  .kopf dl { margin: 0; font-size: 9pt; }
  .kopf dt { color: #666; }
  .kopf dd { margin: 0 0 1.5mm 0; }
  table { width: 100%; border-collapse: collapse; margin-top: 6mm; }
  th { text-align: left; font-size: 8pt; text-transform: uppercase;
       letter-spacing: .04em; color: #666; border-bottom: .8pt solid #333;
       padding-bottom: 1.5mm; }
  td { padding: 2mm 0; border-bottom: .3pt solid #ddd;
       font-variant-numeric: tabular-nums; }
  .r { text-align: right; }
  td:nth-child(4), th:nth-child(4) { padding-left: 3mm; }
  tfoot td { border: 0; padding: 1mm 0; }
  tfoot .summe td { border-top: .8pt solid #333; font-weight: 600;
                    padding-top: 2mm; }
  .fuss { margin-top: 16mm; font-size: 8pt; color: #666;
          border-top: .5pt solid #bbb; padding-top: 3mm; }
  .hinweis { margin-top: 8mm; font-size: 8pt; color: #444;
             background: #f4f4f2; padding: 3mm 4mm; }
</style>
"""


def euro(betrag: Decimal) -> str:
    text = f'{betrag:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{text} &euro;'


def zahl(wert: str) -> str:
    d = Decimal(wert)
    text = f'{d.normalize():f}' if d != d.to_integral() else f'{int(d)}'
    return text.replace('.', ',')


def tag(d: date) -> str:
    return d.strftime('%d.%m.%Y')


def iban_lesbar(iban: str) -> str:
    return ' '.join(iban[i:i + 4] for i in range(0, len(iban), 4))


def seite(r: Rechnung) -> str:
    l = r.lieferant
    kopf = [('Rechnungsnummer', r.nummer), ('Rechnungsdatum', tag(r.datum)),
            ('Leistungsdatum', tag(r.leistung))]
    if r.bestellung:
        kopf.append(('Ihre Bestellung', r.bestellung))
    if r.projektreferenz:
        kopf.append(('Bauvorhaben', r.projektreferenz))
    kopf.append(('USt-IdNr.', l.ust_id))

    zeilen = ''.join(
        f'<tr><td>{i}</td><td>{bez}</td><td class="r">{zahl(menge)}</td>'
        f'<td>{einheit}</td><td class="r">{euro(Decimal(preis))}</td>'
        f'<td class="r">{euro(zeile_betrag((bez, menge, einheit, preis)))}'
        f'</td></tr>'
        for i, (bez, menge, einheit, preis) in enumerate(r.positionen, 1))

    if r.erechnung:
        hinweis = ('<strong>Beispieldatei</strong> aus dem Vorführbestand von '
                   'paper-werk. Erfundene Rechnung &ndash; kein Zahlungsbeleg, '
                   'keine Buchungsgrundlage. In diesem PDF steckt eine '
                   'E-Rechnung (Factur-X, EN&nbsp;16931) als Anhang '
                   '<em>factur-x.xml</em>.')
    else:
        hinweis = ('<strong>Beispieldatei</strong> aus dem Vorführbestand von '
                   'paper-werk. Erfundene Rechnung &ndash; kein Zahlungsbeleg, '
                   'keine Buchungsgrundlage.')

    return f"""{STIL}
<div class="firma">{l.name}</div>
<div class="absender">{l.name} &middot; {l.strasse} &middot; {l.plz} {l.ort}</div>
<div class="kopf">
  <div>
    <h1>Rechnung</h1>
    <div style="font-size:9pt;color:#666">Nr. {r.nummer}</div>
    <div style="margin-top:8mm;font-size:9.5pt;line-height:1.5">
      {KAEUFER['name']}<br>{KAEUFER['strasse']}<br>
      {KAEUFER['plz']} {KAEUFER['ort']}
    </div>
  </div>
  <dl>{''.join(f'<dt>{a}</dt><dd>{b}</dd>' for a, b in kopf)}</dl>
</div>
<p style="font-size:9.5pt;font-weight:600">{r.betreff}</p>
<table>
  <thead><tr><th>Pos.</th><th>Leistung</th><th class="r">Menge</th>
    <th>Einheit</th><th class="r">Einzelpreis</th><th class="r">Betrag</th>
  </tr></thead>
  <tbody>{zeilen}</tbody>
  <tfoot>
    <tr><td colspan="5" class="r">Summe netto</td>
        <td class="r">{euro(r.netto)}</td></tr>
    <tr><td colspan="5" class="r">zzgl. 19 % USt</td>
        <td class="r">{euro(r.steuer)}</td></tr>
    <tr class="summe"><td colspan="5" class="r">Rechnungsbetrag</td>
        <td class="r">{euro(r.brutto)}</td></tr>
  </tfoot>
</table>
<p style="margin-top:8mm;font-size:9pt">
  Zahlbar ohne Abzug bis zum {tag(r.faellig)} auf
  IBAN {iban_lesbar(l.iban)} ({l.bank}).
</p>
<div class="hinweis">{hinweis}</div>
<div class="fuss">
  {l.name} &middot; {l.strasse}, {l.plz} {l.ort} &middot;
  USt-IdNr. {l.ust_id} &middot; {l.bank} &middot; IBAN {iban_lesbar(l.iban)}
</div>
"""


# ══════════════════════════════════════════════════════════════════════════
# Das XML (CII nach EN 16931)
# ══════════════════════════════════════════════════════════════════════════

def _d(d: date) -> str:
    return f'<udt:DateTimeString format="102">{d:%Y%m%d}</udt:DateTimeString>'


def _x(text: str) -> str:
    return (text.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))


def xml(r: Rechnung) -> bytes:
    l = r.lieferant
    zeilen = []
    for i, (bez, menge, einheit, preis) in enumerate(r.positionen, 1):
        zeilen.append(f"""
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument><ram:LineID>{i}</ram:LineID></ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct><ram:Name>{_x(bez)}</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice><ram:ChargeAmount>{Decimal(preis):.2f}</ram:ChargeAmount></ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="{EINHEIT_CODE[einheit]}">{Decimal(menge)}</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:ApplicableTradeTax>
          <ram:TypeCode>VAT</ram:TypeCode><ram:CategoryCode>S</ram:CategoryCode>
          <ram:RateApplicablePercent>{UST:.2f}</ram:RateApplicablePercent>
        </ram:ApplicableTradeTax>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>{zeile_betrag((bez, menge, einheit, preis)):.2f}</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>""")

    bestellung = (f"""
      <ram:BuyerOrderReferencedDocument>
        <ram:IssuerAssignedID>{_x(r.bestellung)}</ram:IssuerAssignedID>
      </ram:BuyerOrderReferencedDocument>""" if r.bestellung else '')
    projekt = (f"""
      <ram:SpecifiedProcuringProject>
        <ram:ID>{_x(r.projektreferenz)}</ram:ID>
        <ram:Name>Bauvorhaben</ram:Name>
      </ram:SpecifiedProcuringProject>""" if r.projektreferenz else '')

    text = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{_x(r.nummer)}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>{_d(r.datum)}</ram:IssueDateTime>
    <ram:IncludedNote><ram:Content>{_x(r.betreff)}</ram:Content></ram:IncludedNote>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>{''.join(zeilen)}
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>{_x(l.name)}</ram:Name>
        <ram:PostalTradeAddress>
          <ram:PostcodeCode>{l.plz}</ram:PostcodeCode>
          <ram:LineOne>{_x(l.strasse)}</ram:LineOne>
          <ram:CityName>{_x(l.ort)}</ram:CityName>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="VA">{l.ust_id}</ram:ID>
        </ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>{_x(KAEUFER['name'])}</ram:Name>
        <ram:PostalTradeAddress>
          <ram:PostcodeCode>{KAEUFER['plz']}</ram:PostcodeCode>
          <ram:LineOne>{_x(KAEUFER['strasse'])}</ram:LineOne>
          <ram:CityName>{KAEUFER['ort']}</ram:CityName>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
      </ram:BuyerTradeParty>{bestellung}{projekt}
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery>
      <ram:ActualDeliverySupplyChainEvent>
        <ram:OccurrenceDateTime>{_d(r.leistung)}</ram:OccurrenceDateTime>
      </ram:ActualDeliverySupplyChainEvent>
    </ram:ApplicableHeaderTradeDelivery>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementPaymentMeans>
        <ram:TypeCode>58</ram:TypeCode>
        <ram:PayeePartyCreditorFinancialAccount>
          <ram:IBANID>{l.iban}</ram:IBANID>
        </ram:PayeePartyCreditorFinancialAccount>
      </ram:SpecifiedTradeSettlementPaymentMeans>
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>{r.steuer:.2f}</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>{r.netto:.2f}</ram:BasisAmount>
        <ram:CategoryCode>S</ram:CategoryCode>
        <ram:RateApplicablePercent>{UST:.2f}</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      <ram:SpecifiedTradePaymentTerms>
        <ram:Description>Zahlbar ohne Abzug bis zum {tag(r.faellig)}.</ram:Description>
        <ram:DueDateDateTime>{_d(r.faellig)}</ram:DueDateDateTime>
      </ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>{r.netto:.2f}</ram:LineTotalAmount>
        <ram:TaxBasisTotalAmount>{r.netto:.2f}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">{r.steuer:.2f}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{r.brutto:.2f}</ram:GrandTotalAmount>
        <ram:DuePayableAmount>{r.brutto:.2f}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
    return text.encode('utf-8')


def main() -> None:
    for r in RECHNUNGEN:
        pdf = faktura_pdf.weasyprint.HTML(string=seite(r)).write_pdf(
            pdf_variant='pdf/a-3b')
        if r.erechnung:
            daten = xml(r)
            # Gegenlesen mit dem Leser der App, bevor etwas geschrieben wird.
            gelesen = erechnung.lesen(daten)
            assert gelesen.betrag_netto == r.netto, (r.datei, gelesen.betrag_netto)
            assert gelesen.lieferant == r.lieferant.name
            pdf = attach_xml(pdf, daten, level='EN 16931')
            assert erechnung.lesen(pdf).nummer == r.nummer
        else:
            assert not erechnung.enthaelt_erechnung(pdf), r.datei
        (BASIS / r.datei).write_bytes(pdf)
        art = 'E-Rechnung' if r.erechnung else 'PDF      '
        print(f'{art}  {r.datei:<38} netto {r.netto:>9}  brutto {r.brutto:>9}')


if __name__ == '__main__':
    main()
