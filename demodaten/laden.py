# Liest einen Bestand ein; läuft IM Container, in der Django-Shell.
#
# Aufgerufen wird das hier nie von Hand, sondern von einspielen.sh:
#
#     docker exec <app> .../python manage.py shell -c "exec(open('/tmp/laden.py').read())"
#
# **Warum dieses Skript hier liegt und nicht in paper-werk-app.** Demodaten
# und Produkt dürfen sich nicht mischen: Was ein Kunde bekommt, soll keine
# erfundenen Betriebe enthalten, weder als Daten noch als Programm, das
# welche anlegen kann. Ein Management-Befehl in der App wäre bequemer und
# wäre trotzdem falsch am Platz.
#
# Der Preis dafür steht hier offen: Dieses Skript hat keine Tests. Es läuft
# gegen die Modelle der App und bricht, wenn die sich ändern. Das ist die
# bewusste Abwägung: Demodaten liegen in der Verantwortung dessen, der sie
# einspielt, und die Anwendung enthält keine.
#
# **Es kennt genau ein Szenario: frische Installation, Bestand einspielen.**
# Kein Nachladen, kein Zusammenführen, kein Fortschreiben. Wer es auf einen
# gefüllten Bestand loslässt, bekommt doppelte Kunden oder einen Abbruch.
# Vor einem zweiten Lauf gehört die Datenbank geleert.
#
# Das Format eines Bestandsverzeichnisses steht in
# demodaten/00-liesmich.md, dort in der Sprache dessen, der einen
# Bestand schreibt. Kurz: nummerierte JSON-Dateien, die Nummer ist die
# Reihenfolge, der Name ist die Art (04-kunden.json), Verweise laufen über
# Namen, Datumsangaben sind relativ zu heute, Felder mit führendem _ sind
# Kommentare.
#
# Umlaute stehen in diesem Skript bewusst nicht: Es geht durch docker exec
# und eine Shell-Umleitung, und auf dem Weg ist schon genug schiefgegangen.
# Die Daten selbst sind davon nicht betroffen; die kommen als UTF-8 aus
# einer Datei.

import json
import sys
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from erfassung.models import (
    Eingangsrechnung,
    Erfassungszeile,
    Fremdleistung,
    Kostensatz,
)
from erfassung.services import in_rechnung_uebernehmen, zeile_erfassen
from faktura import services as faktura_services
from faktura import standardtexte
from faktura.models import (
    Adresse,
    Ansprechpartner,
    Beleg,
    BelegStatus,
    BelegTyp,
    Firma,
    Katalogposition,
    Kontaktweg,
    Kontakt,
    Leistungsart,
    Projekt,
    Rechnungsart,
    Textbaustein,
    TextbausteinVerwendung,
    Zahlung,
    Zahlungszuordnung,
)
from faktura.models.steuersatz import vorgabe as steuersatz_vorgabe

#: Wohin einspielen.sh das gebündelte Bestandsverzeichnis gelegt hat.
BUENDEL = '/tmp/demodaten.json'

#: Woran eine Einheit ihre Erfassungsart erkennen lässt.
#
# Nur ein Rückfall: Steht die Leistung im Katalog, gilt dessen Art. Frei
# getextete Positionen stehen dort nicht, und ohne Art zeigte die
# Erfassungsmaske ein Mengenfeld statt zweier Uhrzeiten.
ART_JE_EINHEIT = {
    'std': Leistungsart.ZEIT,
    'h': Leistungsart.ZEIT,
    'psch': Leistungsart.PAUSCHALE,
    'pauschal': Leistungsart.PAUSCHALE,
}


def abbruch(text):
    """Beendet den Lauf mit einer Meldung.

    Die Transaktion drumherum nimmt alles zurück: Ein Bestand, der zur
    Hälfte einläuft, ist schlimmer als einer, der gar nicht läuft: Man
    sieht Daten und glaubt, es habe geklappt.
    """
    print(f'FEHLER: {text}', file=sys.stderr)
    raise SystemExit(1)


def sauber(inhalt):
    """Wirft alle Felder mit führendem _ weg, überall, auch verschachtelt.

    So darf _kommentar an jeder Stelle stehen, an der eine Erklärung
    hingehört, ohne dass der Lader jede einzelne kennen muss. Dieselbe
    Konvention wie in den Paperless-Starterpaketen.
    """
    if isinstance(inhalt, dict):
        return {k: sauber(v) for k, v in inhalt.items()
                if not k.startswith('_')}
    if isinstance(inhalt, list):
        return [sauber(e) for e in inhalt]
    return inhalt


class Lader:
    """Haelt die Nachschlagetabellen, waehrend die Dateien gelesen werden."""

    def __init__(self):
        self.heute = timezone.localdate()
        # Was die Dateien untereinander per Namen ansprechen. Wird gefüllt,
        # während gelesen wird. Deshalb ist die Reihenfolge der Dateien
        # fachlich zwingend und nicht Geschmackssache.
        self.katalog = {}
        self.leute = {}
        self.kunden = {}
        self.lieferanten = {}
        self.projekte = {}
        # Nummernvorlage -> tatsächliche Nummer, siehe jahr().
        self.nummern = {}
        # (Person, Tag) -> gebuchte Zeitfenster, siehe erfassen().
        self.belegt = {}

    # -- Der Lauf ------------------------------------------------------------

    def alles(self, dateien):
        arten = {
            'betrieb': self.betrieb,
            'katalog': self.katalog_anlegen,
            'mannschaft': self.mannschaft,
            'kunden': self.kunden_anlegen,
            'lieferanten': self.lieferanten_anlegen,
            'kleinauftraege': self.kleinauftraege,
            'projekte': self.projekte_anlegen,
            # Dieselbe Bauform wie "projekte", nur ein anderer Dateiname:
            # abgeschlossene Vorhaben, die den Zwölf-Monats-Verlauf füllen.
            # Ohne sie steht auf der Startseite eine leere Fläche mit einem
            # Balken rechts.
            'vorgeschichte': self.projekte_anlegen,
            'einkauf': self.einkauf,
            # Nach dem Einkauf: Eine Abrechnung übernimmt auch
            # Fremdleistungen, und die gibt es erst ab hier.
            'abrechnungen': self.abrechnungen,
            'mahnungen': self.mahnungen,
            # Steht am Ende eines Bestands: Zugeordnet wird über die
            # Belegnummer, und die gibt es erst nach der Festschreibung.
            'zahlungen': self.zahlungen,
            'textbausteine': self.textbausteine,
        }
        for datei in dateien:
            name = datei['name']
            # Die Art steht im Dateinamen hinter der Nummer: 04-kunden.json.
            # Ein unbekannter Name ist ein Fehler und kein stilles Übergehen -
            # sonst vertippt man sich einmal in kundne.json und sucht danach
            # den fehlenden Bestand.
            art = name.rsplit('.', 1)[0].split('-', 1)[-1]
            if art not in arten:
                abbruch(f'{name}: unbekannte Art "{art}". '
                        f'Bekannt sind: {", ".join(sorted(arten))}.')
            arten[art](sauber(datei['inhalt']))
            print(f'  {name}')

    # -- Die Arten, je eine Methode ------------------------------------------

    def betrieb(self, daten):
        firma = Firma.objects.create(**daten)
        self.standardtexte(firma)

    def standardtexte(self, firma):
        """Die Standard-Textbausteine der App, mit dem Namen dieser Firma.

        **Die Texte selbst stehen nicht im Bestand**, sondern in
        paper-werk-app (faktura/standardtexte.py): Sie sind Grundausstattung
        jeder Anlage und keine Demodaten. Im Bestand stünden sie ein
        zweites Mal und liefen beim nächsten Umformulieren auseinander. Was
        ein Betrieb über diese hinaus hat, steht in NN-textbausteine.json.

        **Warum sie trotzdem hier angelegt werden.** Ein Bestand soll auch
        auf einer Anlage vollständig sein, deren Setup sie noch nicht
        mitgebracht hat.

        **Und warum die Grussformel nachgezogen wird.** Das Setup läuft vor
        dem Bestand, und zu dem Zeitpunkt gibt es keine Firma: Die Formel
        entsteht ohne Namenszeile. Ersetzt wird sie nur, solange sie
        unverändert ist; ein Wortlaut, den jemand angepasst hat, bleibt.
        """
        standardtexte.anlegen(firma)
        Textbaustein.objects.filter(
            name=standardtexte.GRUSSFORMEL,
            text=standardtexte.grussformel(''),
        ).update(text=standardtexte.grussformel(firma.name))

    def katalog_anlegen(self, eintraege):
        for e in eintraege:
            position = Katalogposition.objects.create(
                nummer=e.get('nummer', ''),
                bezeichnung=e['bezeichnung'],
                langtext=e.get('langtext', ''),
                einheit=e.get('einheit', 'Stk'),
                einzelpreis=Decimal(e['preis']),
                steuersatz=e.get('steuersatz', steuersatz_vorgabe()),
                kontierbar=e.get('kontierbar', True),
                art=e.get('art', Leistungsart.MENGE),
            )
            self.katalog[position.bezeichnung] = position

    def mannschaft(self, eintraege):
        """Personen und ihre Kostensätze.

        Das Kennwort bleibt unbrauchbar: Diese Konten sind zum Zuordnen von
        Stunden da, nicht zum Anmelden. Wer sich anmelden können soll,
        bekommt sein Kennwort ausdrücklich gesetzt.
        """
        for e in eintraege:
            person = get_user_model().objects.create(
                username=e['anmeldename'],
                first_name=e.get('vorname', ''),
                last_name=e.get('nachname', ''),
                is_staff=True,
            )
            person.set_unusable_password()
            person.save()

            for satz in e.get('kostensaetze', []):
                Kostensatz.objects.create(
                    benutzer=person,
                    gueltig_ab=self.heute - timedelta(
                        days=self.tage_zurueck(satz)),
                    satz=Decimal(satz['satz']),
                    notiz=satz.get('notiz', ''),
                )
            self.leute[person.username] = person

    def kunden_anlegen(self, eintraege):
        """Kunden samt Anschriften, Kontaktwegen und Ansprechpartnern.

        **Die flache Zeile bleibt die Regel.** Strasse, plz, ort, land,
        email und telefon stehen weiterhin direkt am Eintrag, obwohl sie
        nicht Spalten der Kundentabelle sind -
        ``Kontakt.anlegen`` verteilt sie auf Adresse und Kontaktwege. Wer
        einen Bestand schreibt, soll sich mit vier Tabellen nicht
        beschaeftigen muessen.

        Wer mehr braucht, haengt zwei Listen an:

            "adressen": [{"verwendung": "rechnung", "strasse": ..., ...}]
            "leute": [{"anrede": "frau", "nachname": ..., "email": ...}]

        Beides ist freiwillig. Das Ingenieurbuero nutzt es, weil genau das
        sein Fall ist: ein Landratsamt mit Fachamt und Rechnungspruefung
        an verschiedenen Adressen.
        """
        for e in eintraege:
            adressen = e.pop('adressen', [])
            leute = e.pop('leute', [])
            kunde = Kontakt.anlegen(**e)
            for a in adressen:
                Adresse.objects.create(kontakt=kunde, **a)
            for person in leute:
                self.ansprechpartner_anlegen(kunde, person)
            self.kunden[kunde.name] = kunde

    def ansprechpartner_anlegen(self, kunde, daten):
        """Eine Person samt ihren eigenen Kontaktwegen.

        E-Mail und Telefon stehen flach am Eintrag, mit derselben Bequemlichkeit
        wie beim Kunden und aus demselben Grund.
        """
        email = daten.pop('email', '')
        telefon = daten.pop('telefon', '')
        person = Ansprechpartner.objects.create(kontakt=kunde, **daten)
        for wert, art in ((email, 'email'), (telefon, 'telefon')):
            if wert:
                Kontaktweg.objects.create(
                    ansprechpartner=person, art=art, wert=wert,
                    ist_standard=True)
        return person

    def zahlungen(self, eintraege):
        """Zahlungseingaenge auf bereits festgeschriebene Rechnungen.

        **Steht am Ende eines Bestands**, denn es braucht die Rechnungen.

        **Verwiesen wird ueber den Betreff, nicht ueber die Belegnummer** -
        dieselbe Entscheidung wie bei den Mahnungen und aus demselben
        Grund: Die Nummer vergibt der Nummernkreis bei der Festschreibung,
        sie steht also nirgends im Bestand und waere je Anlage eine andere.
        Der Betreff dagegen ist das, was derjenige hingeschrieben hat, der
        den Bestand baut.

        **Der Betrag darf fehlen.** Steht kein ``betrag`` an der Zuordnung,
        wird die Rechnung vollstaendig ausgeglichen. Das ist der
        Regelfall und erspart es, Bruttobetraege von Hand auszurechnen und
        bei jeder Preisaenderung nachzuziehen. Wer eine Teilzahlung zeigen
        will, nennt den Betrag.

        Eine Rechnung, die hier nicht genannt ist, bleibt offen, und
        genau das ist der Zweck. Ohne unbezahlte Rechnungen ist die Liste
        der offenen Posten leer, und eine leere Liste zeigt nichts.
        """
        for e in eintraege:
            zuordnungen = e.pop('zuordnungen', [])
            kundenname = e.pop('kunde', '')
            tage = self.tage_zurueck(e)
            e.pop('vor_tagen', None)
            e.pop('vor_monaten', None)
            betrag = e.pop('betrag', None)

            posten = [(self.rechnung_zu(z['rechnung']), z) for z in zuordnungen]
            ausgleiche = [
                (beleg, z, (Decimal(z['betrag']) if 'betrag' in z
                            else faktura_services.belegsummen(beleg).brutto
                            - Decimal(z.get('skonto', '0.00'))))
                for beleg, z in posten
            ]
            zahlung = Zahlung.objects.create(
                datum=self.heute - timedelta(days=tage),
                betrag=(Decimal(betrag) if betrag is not None
                        else sum((wert for _, _, wert in ausgleiche),
                                 Decimal('0.00'))),
                kunde=self.kunden.get(kundenname),
                **e,
            )
            for beleg, z, wert in ausgleiche:
                Zahlungszuordnung.objects.create(
                    zahlung=zahlung,
                    beleg=beleg,
                    betrag=wert,
                    skonto=Decimal(z.get('skonto', '0.00')),
                )

    def rechnung_zu(self, betreff):
        """Die festgeschriebene Rechnung mit diesem Betreff.

        Dieselbe Aufloesung wie bei den Mahnungen, samt der Ersetzung von
        ``{vorjahr}`` durch ``self.jahr()``.
        """
        gesucht = self.jahr(betreff)
        beleg = (Beleg.objects
                 .filter(typ=BelegTyp.RECHNUNG, betreff=gesucht)
                 .exclude(nummer=None)
                 .first())
        if beleg is None:
            abbruch(f'Zahlung: Keine festgeschriebene Rechnung mit dem '
                    f'Betreff "{gesucht}".')
        return beleg

    def lieferanten_anlegen(self, eintraege):
        """Lieferanten sind Kontakte mit der Rolle Lieferant. Steht derselbe
        Name schon unter den Kunden, bekommt dieser Kontakt die Rolle dazu -
        wie beim Import aus Archiv und E-Rechnung."""
        for e in eintraege:
            kontakt = self.kunden.get(e['name'])
            if kontakt is None:
                kontakt = Kontakt.objects.create(
                    ist_kunde=False, ist_lieferant=True, **e)
            else:
                kontakt.ist_lieferant = True
                kontakt.eigene_kundennummer = e.get('eigene_kundennummer', '')
                kontakt.save(update_fields=['ist_lieferant',
                                            'eigene_kundennummer'])
            self.lieferanten[kontakt.name] = kontakt

    def textbausteine(self, eintraege):
        """Die Bausteine, die dieser Betrieb über die Standardtexte hinaus hat.

        Die Standardtexte selbst kommen aus der App (siehe
        ``standardtexte``); hier steht nur, was zum Gewerk gehört: der
        Hinweis auf 35a beim Handwerker, die Absetzung der Abschläge beim
        Ingenieurbüro.

        **Ein Name, den es schon gibt, ist ein Abbruch.** Namen sind
        eindeutig, und ein Bestand, der "Anrede" neu formulieren will,
        überschriebe still einen Standardtext. Wer das wirklich will,
        nennt seinen Baustein anders.

        ``verwendung`` ist ohne Angabe ``belegtext``, ``belegart`` ohne
        Angabe leer, also für jede Belegart. Dieselben Vorgaben wie im
        Modell.
        """
        verwendungen = {w.value for w in TextbausteinVerwendung}
        belegarten = {t.value for t in BelegTyp}
        for e in eintraege:
            name = e['name']
            verwendung = e.get('verwendung', TextbausteinVerwendung.BELEGTEXT)
            belegart = e.get('belegart', '')
            if verwendung not in verwendungen:
                abbruch(f'Textbaustein "{name}": unbekannte Verwendung '
                        f'"{verwendung}". Bekannt sind: '
                        f'{", ".join(sorted(verwendungen))}.')
            if belegart and belegart not in belegarten:
                abbruch(f'Textbaustein "{name}": unbekannte Belegart '
                        f'"{belegart}". Bekannt sind: '
                        f'{", ".join(sorted(belegarten))}.')
            if Textbaustein.objects.filter(name=name).exists():
                abbruch(f'Textbaustein "{name}" gibt es schon - ein '
                        f'Standardtext oder ein zweiter Eintrag im Bestand. '
                        f'Bitte anders benennen.')
            Textbaustein.objects.create(
                name=name, verwendung=verwendung, belegart=belegart,
                text=e['text'],
            )

    def kleinauftraege(self, eintraege):
        """Rechnungen ohne Projekt, direkt an den Kunden.

        Für einen Handwerksbetrieb der Alltag: Steckdose getauscht, E-Check
        gemacht, fertig. Ein Beleg trägt Kunde ODER Projekt, nie beides.
        """
        for e in eintraege:
            self.wertbeleg(
                typ=BelegTyp.RECHNUNG,
                kunde=self.kunde(e['kunde']),
                betreff=e['betreff'],
                kopftext=e.get('kopftext', ''),
                positionen=e['positionen'],
                tage=self.tage_zurueck(e),
                von_tagen=e.get('leistung_von_tagen'),
                bis_tagen=e.get('leistung_bis_tagen'),
            )

    def projekte_anlegen(self, eintraege):
        for e in eintraege:
            projekt = Projekt.objects.create(
                nummer=self.projektnummer(e),
                bezeichnung=e['bezeichnung'],
                kunde=self.kunde(e['kunde']),
                beschreibung=e.get('beschreibung', ''),
            )
            self.projekte[projekt.nummer] = projekt
            self.nummern[e['nummer']] = projekt.nummer
            auftrag = self.auftrag(projekt, e.get('auftrag'))

            for zeile in e.get('stunden', []):
                self.erfassen(projekt, auftrag, zeile, zeit=True)
            for zeile in e.get('mengen', []):
                self.erfassen(projekt, auftrag, zeile, zeit=False)

            for abschlag in e.get('abschlaege', []):
                self.abschlag(projekt, auftrag, abschlag)
            for nachtrag in e.get('nachtraege', []):
                self.nachtrag(projekt, auftrag, nachtrag)
            if 'schlussrechnung' in e:
                self.schlussrechnung(projekt, auftrag, e['schlussrechnung'])

            # Freie Belege am Projekt: ein Angebot, auf das noch keine
            # Antwort da ist, oder eine gewöhnliche Rechnung mit eigenen
            # Preisen. Anders als "auftrag" tragen sie einen eigenen Betreff
            # und werden nicht bebucht.
            for typ, schluessel in ((BelegTyp.ANGEBOT, 'angebote'),
                                    (BelegTyp.RECHNUNG, 'rechnungen')):
                for beleg in e.get(schluessel, []):
                    self.wertbeleg(
                        typ=typ, projekt=projekt,
                        # "{nummer}" im Betreff wird zur Projektnummer -
                        # sonst müsste eine Schlussrechnung die Nummer
                        # ihres Vorhabens zweimal tragen, und beim Ändern
                        # vergisst man die zweite.
                        betreff=self.jahr(beleg['betreff']).replace(
                            '{nummer}', projekt.nummer),
                        kopftext=beleg.get('kopftext', ''),
                        positionen=self.positionen(beleg, auftrag),
                        tage=self.tage_zurueck(beleg),
                        von_tagen=beleg.get('leistung_von_tagen'),
                        bis_tagen=beleg.get('leistung_bis_tagen'),
                    )

            if e.get('abgeschlossen'):
                # Erst zum Schluss: Ein abgeschlossenes Vorhaben fällt aus
                # den Auswertungen heraus, und die Belege oben sollen
                # vorher entstehen.
                projekt.abgeschlossen = True
                projekt.save(update_fields=['abgeschlossen'])

    # -- Die Bausteine eines Projekts ----------------------------------------

    def auftrag(self, projekt, angaben):
        """Angebot und, wenn beauftragt, der Auftrag dazu.

        Beide werden festgeschrieben. Nur so zählen sie in den
        Projektständen: Entwürfe bleiben dort ausdrücklich draußen, und
        ein Bestand aus lauter Entwürfen zeigte überall Nullen.

        Zurück kommt der Auftrag, denn auf seine Positionen wird kontiert.
        Ohne Beauftragung bleibt es beim Angebot und der Rückgabewert leer -
        dann buchen Stunden über den Katalog, und genau das soll in einem
        Bestand auch vorkommen.
        """
        if not angaben:
            return None

        auftrag = None
        stationen = []
        # "mit_angebot": false gibt es für den Fall, dass ein Vorhaben ohne
        # vorheriges Angebot beauftragt wurde. Das kommt vor, und ein Bestand,
        # in dem JEDES Vorhaben ein Angebot hat, sieht danach aus, als wäre
        # er erfunden.
        if angaben.get('mit_angebot', True):
            stationen.append(
                (BelegTyp.ANGEBOT, angaben.get('angebot_vor_tagen', 75)))
        if angaben.get('beauftragt'):
            stationen.append(
                (BelegTyp.AUFTRAG, angaben.get('auftrag_vor_tagen', 68)))

        for typ, tage in stationen:
            beleg = self.wertbeleg(
                typ=typ, projekt=projekt, betreff=projekt.bezeichnung,
                positionen=angaben['positionen'], tage=tage,
            )
            if typ == BelegTyp.AUFTRAG:
                auftrag = beleg
        return auftrag

    def erfassen(self, projekt, auftrag, zeile, zeit):
        """Erfasste Leistungen an bestimmten Tagen.

        **Am Wochenende wird nicht gebucht.** Ein Bestand, in dem
        durchgearbeitet wird, fällt jedem Praktiker sofort auf; die Tage
        fallen deshalb still weg statt zu Samstagsstunden zu werden.

        Gebucht wird auf die Auftragsposition derselben Leistung, wo es eine
        gibt; dann kommt der Preis aus dem Vertrag. Sonst über den Katalog.

        **Niemand ist zur selben Zeit an zwei Orten.** Überschneidet sich
        eine Zeile mit einer schon gebuchten derselben Person, bricht der
        Lauf ab, damit kein Bestand eine Person auf mehrere Vorhaben
        zugleich bucht.
        """
        leistung = self.leistung(zeile['leistung'])
        # "ohne_auftrag": true bucht über den Katalog, obwohl es eine
        # passende Auftragsposition gäbe. Das gehört in einen Bestand: In
        # der Erfassungsmaske gibt es die Gruppe "Ohne Auftrag", und die
        # wäre sonst nie belegt.
        position = (None if zeile.get('ohne_auftrag')
                    else self.auftragsposition(auftrag, zeile['leistung']))
        person = self.person(zeile['person'])

        for abstand in zeile['vor_tagen']:
            tag = self.heute - timedelta(days=abstand)
            if tag.weekday() >= 5:
                continue
            if zeit:
                self.zeitfenster_belegen(person, tag, zeile, projekt)
            zeile_erfassen(
                projekt=projekt, benutzer=person,
                leistung=None if position else leistung,
                auftragsposition=position,
                beschreibung=zeile.get('beschreibung', ''),
                datum=tag,
                von=zeile['von'] if zeit else None,
                bis=zeile['bis'] if zeit else None,
                menge=None if zeit else Decimal(zeile['menge']),
            )

    def zeitfenster_belegen(self, person, tag, zeile, projekt):
        """Merkt sich das Zeitfenster oder bricht ab, wenn die Person
        dann schon woanders gebucht ist. Verglichen wird als (Stunde,
        Minute), damit "8:00" und "08:00" dasselbe sind."""
        def uhrzeit(text):
            return tuple(int(teil) for teil in text.split(':'))

        von, bis = uhrzeit(zeile['von']), uhrzeit(zeile['bis'])
        gebucht = self.belegt.setdefault((person.pk, tag), [])
        for anderes_von, anderes_bis, anderes in gebucht:
            if von < anderes_bis and anderes_von < bis:
                abbruch(f'{person.username} am {tag:%d.%m.%Y}: '
                        f'{zeile["von"]}-{zeile["bis"]} in {projekt.nummer} '
                        f'überschneidet sich mit einer Zeile in {anderes}. '
                        f'Eine Person ist nicht an zwei Orten zugleich - '
                        f'bitte die Tage oder Uhrzeiten auseinanderlegen.')
        gebucht.append((von, bis, projekt.nummer))

    def abschlag(self, projekt, auftrag, angaben):
        """Eine Abschlagsrechnung auf den Auftrag.

        Die Positionen tragen nur Bezeichnung und Menge; Einheit und Preis
        holt der Abschlag aus der Auftragsposition, **also aus dem Vertrag**,
        wie es die Abrechnung über Positionen vorsieht.

        **``bezahlt_vor_tagen`` bucht die Zahlung gleich hier**, voll und an
        diesem Tag, nicht in ``zahlungen``. Die stehen am Ende des
        Bestands, also nach der Schlussrechnung; die setzt netto nur ab, was vereinnahmt ist, und fordert den Rest selbst
        (Rechenregister R-174). Eine Zahlung danach stünde doppelt da.
        """
        if auftrag is None:
            abbruch(f'{projekt.nummer}: Abschlag ohne Auftrag. Ein Abschlag '
                    f'rechnet aus dem Vertrag ab; ohne "auftrag" mit '
                    f'"beauftragt": true gibt es keinen.')

        belegtag = self.heute - timedelta(days=self.tage_zurueck(angaben))
        beleg = faktura_services.beleg_anlegen(
            projekt=projekt, typ=BelegTyp.RECHNUNG,
            rechnungsart=Rechnungsart.ABSCHLAG,
            # "1. Abschlag {nummer}": Mehrere Abschläge eines Vorhabens
            # brauchen verschiedene Betreffe, sonst trifft eine Zahlung
            # (``rechnung_zu``) immer den ersten.
            betreff=self.jahr(angaben.get(
                'betreff', 'Abschlag {nummer}')).replace(
                    '{nummer}', projekt.nummer),
            kopftext=angaben.get(
                'kopftext',
                'für die bisher erbrachten Leistungen berechnen wir '
                'Ihnen vereinbarungsgemäß einen Abschlag:'),
            # Wie beim Wertbeleg: ab dem Belegdatum zurück, nicht ab heute.
            leistungsdatum=belegtag - timedelta(
                days=angaben['leistung_von_tagen']),
            leistungsdatum_bis=belegtag - timedelta(
                days=angaben['leistung_bis_tagen']),
        )
        for p in angaben['positionen']:
            position = self.auftragsposition(auftrag, p['leistung'])
            if position is None:
                abbruch(f'{projekt.nummer}: "{p["leistung"]}" steht nicht im '
                        f'Auftrag. Ein Abschlag auf etwas Unbeauftragtes '
                        f'waere ein Fehler im Bestand.')
            faktura_services.position_hinzufuegen(
                beleg=beleg, bezeichnung=p['leistung'],
                menge=Decimal(p['menge']), einheit=position.einheit,
                einzelpreis=position.einzelpreis,
                steuersatz=position.steuersatz, art=position.art,
                auftragsposition=position,
            )
        beleg = self.festschreiben(beleg, self.tage_zurueck(angaben))
        if 'bezahlt_vor_tagen' in angaben:
            faktura_services.zahlung_verbuchen(
                beleg_id=beleg.pk,
                datum=self.heute - timedelta(days=angaben['bezahlt_vor_tagen']),
                betrag=faktura_services.belegsummen(beleg).brutto,
                verwendungszweck=beleg.nummer)
        return beleg

    def wertbeleg(self, typ, positionen, tage, betreff,
                  projekt=None, kunde=None, kopftext='',
                  von_tagen=None, bis_tagen=None):
        """Ein Beleg mit Positionen, festgeschrieben und richtig datiert.

        Langtext, Einheit und Erfassungsart kommen aus dem Katalog, wenn die
        Leistung dort steht, genau wie bei der Katalogauswahl im
        Belegformular. Ein eigener Preis in der Position schlägt den
        Katalogpreis; das ist der Normalfall, weil ein Vertrag eigene Preise
        haben darf.

        **Der Leistungszeitraum zählt ab dem Belegdatum zurück**, nicht ab
        heute, anders als jede andere Datumsangabe im Format, und deshalb
        heißen die Felder auch anders (leistung_von_tagen statt vor_tagen).
        Fachlich ist es der einzig sinnvolle Bezug: Die Leistung liegt ein
        paar Tage vor der Rechnung, egal wann die geschrieben wurde. Ohne
        Angabe nimmt der Beleg einen Tag 30 Tage vor sich selbst.

        **Angebot und Auftrag schauen nach vorn:** Bei ihnen ist das Feld
        der geplante Ausführungszeitraum, ohne Angabe eine Woche nach dem
        Beleg.

        Eine Position mit ``auftragsposition`` rechnet diese ab
        (``positionen_aus_auftrag``).
        """
        belegtag = self.heute - timedelta(days=tage)
        if von_tagen is None:
            von_tagen = (-7 if typ in (BelegTyp.ANGEBOT, BelegTyp.AUFTRAG)
                         else 30)
        beleg = faktura_services.beleg_anlegen(
            projekt=projekt, kunde=kunde, typ=typ,
            betreff=betreff, kopftext=kopftext,
            leistungsdatum=belegtag - timedelta(days=von_tagen),
            leistungsdatum_bis=(belegtag - timedelta(days=bis_tagen)
                                if bis_tagen is not None else None),
        )
        for p in positionen:
            aus_katalog = self.katalog.get(p['leistung'])
            einheit = p.get(
                'einheit', aus_katalog.einheit if aus_katalog else 'Stk')
            faktura_services.position_hinzufuegen(
                beleg=beleg, bezeichnung=p['leistung'],
                langtext=aus_katalog.langtext if aus_katalog else '',
                menge=Decimal(p['menge']), einheit=einheit,
                einzelpreis=Decimal(
                    p['preis'] if 'preis' in p else aus_katalog.einzelpreis),
                steuersatz=(aus_katalog.steuersatz if aus_katalog
                            else steuersatz_vorgabe()),
                art=self.art(p['leistung'], einheit),
                auftragsposition=p.get('auftragsposition'),
            )
        return self.festschreiben(beleg, tage)

    def schlussrechnung(self, projekt, auftrag, angaben):
        """Die Schlussrechnung mit Absetzung der Abschlaege.

        **Die Absetzung ist der Punkt.** Der Beleg führt die volle Leistung
        auf und zieht die geleisteten Abschlaege wieder ab, so, wie es die
        Praxis verlangt und wie es kein Betrieb von Hand gern rechnet. Ohne
        diesen Fall im Bestand bleibt der Abrechnungsweg auf halber Strecke
        stehen.

        Die Positionen kommen aus dem Auftrag und werden mit ihm verknüpft;
        die Abzüge entstehen aus den Abschlägen, die vorher an diesem
        Vorhaben festgeschrieben wurden.
        """
        if auftrag is None:
            abbruch(f'{projekt.nummer}: Schlussrechnung ohne Auftrag.')

        tage = self.tage_zurueck(angaben)
        belegtag = self.heute - timedelta(days=tage)
        beleg = faktura_services.beleg_anlegen(
            projekt=projekt, typ=BelegTyp.RECHNUNG,
            rechnungsart=Rechnungsart.SCHLUSS,
            betreff=angaben.get('betreff',
                                f'Schlussrechnung {projekt.nummer}'),
            kopftext=angaben.get(
                'kopftext',
                'wir berechnen Ihnen abschließend die erbrachten '
                'Leistungen:'),
            leistungsdatum=belegtag - timedelta(
                days=angaben['leistung_von_tagen']),
            leistungsdatum_bis=belegtag - timedelta(
                days=angaben.get('leistung_bis_tagen', 0)),
        )
        for position in auftrag.positionen.all():
            faktura_services.position_hinzufuegen(
                beleg=beleg, bezeichnung=position.bezeichnung,
                menge=position.menge, einheit=position.einheit,
                einzelpreis=position.einzelpreis,
                steuersatz=position.steuersatz, art=position.art,
                auftragsposition=position,
            )

        # Über denselben Dienst wie in der Maske: je Abschlagsposition eine
        # Abzugszeile mit Verweis auf das, was sie absetzt. Ohne Verweis hielte
        # eine spätere Teilschlussrechnung den Abschlag für nicht abgesetzt.
        faktura_services.abschlaege_absetzen(beleg_id=beleg.pk)
        return self.festschreiben(beleg, tage)

    def nachtrag(self, projekt, auftrag, angaben):
        """Ein Nachtrag zum Hauptauftrag.

        Für eine Vorführung der wichtigste Beleg überhaupt: Er ist die
        Antwort auf die Warnung "über dem Auftrag". Man sieht die
        Ueberschreitung, verhandelt nach, bestaetigt, und die Zahl geht
        zurück. Ohne diesen Fall bliebe die Warnung eine Sackgasse.

        Er ist ein Auftrag wie jeder andere, nur mit einem Verweis auf den
        Hauptauftrag; auf seine Positionen wird ebenso kontiert.
        """
        if auftrag is None:
            abbruch(f'{projekt.nummer}: Nachtrag ohne Hauptauftrag. Ein '
                    f'Nachtrag haengt an einem Auftrag; ohne "auftrag" mit '
                    f'"beauftragt": true gibt es keinen.')

        tage = self.tage_zurueck(angaben)
        beleg = faktura_services.beleg_anlegen(
            projekt=projekt, typ=BelegTyp.AUFTRAG,
            betreff=angaben['betreff'],
            # Geplant ab einer Woche nach dem Nachtrag, wie beim Auftrag.
            leistungsdatum=self.heute - timedelta(days=tage - 7),
        )
        beleg.nachtrag_zu = auftrag
        beleg.save()
        for p in angaben['positionen']:
            einheit = p.get('einheit', self.einheit_aus_katalog(p['leistung']))
            faktura_services.position_hinzufuegen(
                beleg=beleg, bezeichnung=p['leistung'],
                menge=Decimal(p['menge']), einheit=einheit,
                einzelpreis=Decimal(p['preis']), steuersatz=steuersatz_vorgabe(),
                art=self.art(p['leistung'], einheit),
            )
        return self.festschreiben(beleg, tage)

    def einkauf(self, eintraege):
        """Eingangsrechnungen mit ihren Fremdleistungen.

        **Nur der Einkauf**: Eine Fremdleistung kennt
        keinen Verkaufspreis mehr. "leistung" ist freiwillig und nennt die
        beauftragte Leistung; gebucht wird dann auf die Auftragsposition
        derselben Bezeichnung im Auftrag des Projekts, genau wie bei den
        Stunden. Beim Übernehmen in die Rechnung gilt deren Preis, wenn die
        Einheit passt; ohne Auftragsposition wird zum Einkauf durchgereicht.
        Beide Fälle gehören in einen guten Bestand.

        Eine Rechnung darf absichtlich unvollständig verteilt sein: Sie
        steht dann in der Arbeitsliste "Nicht abgerechnet" und wartet auf
        den Rest. Ein Bestand, in dem alles sauber zugeordnet ist, zeigt die
        Liste leer und damit nicht, wozu sie da ist.
        """
        for e in eintraege:
            rechnung = Eingangsrechnung.objects.create(
                lieferant=self.lieferant(e['lieferant']),
                nummer=e['nummer'],
                datum=self.heute - timedelta(days=self.tage_zurueck(e)),
                betrag_netto=Decimal(e['betrag_netto']),
                notiz=e.get('notiz', ''),
            )
            for f in e.get('fremdleistungen', []):
                projekt = self.projekt(f['projekt'])
                Fremdleistung.objects.create(
                    rechnung=rechnung,
                    projekt=projekt,
                    auftragsposition=(
                        self.auftragsposition(self.auftrag_von(projekt),
                                              f['leistung'])
                        if 'leistung' in f else None),
                    bezeichnung=f['bezeichnung'],
                    einheit=f.get('einheit', 'Stk'),
                    menge=Decimal(f['menge']),
                    einkaufspreis=Decimal(f['einkaufspreis']),
                    # Was der Betrieb selbst trägt: eine Nachanalyse nach
                    # eigenem Fehler etwa. Kosten ja, Erlös nein, und
                    # genau das zeigt die Nachkalkulation ehrlich an.
                    weiterberechenbar=f.get('weiterberechenbar', True),
                )

    def abrechnungen(self, eintraege):
        """Rechnungen aus ERFASSTEN Leistungen, über "Erbrachte Leistungen
        hinzufügen", nicht mit eigenen Positionen.

        Erst so hängen Zeiten und Fremdleistungen an der Rechnungsposition,
        und die Akten zeigen, welche Leistung auf welcher Rechnung steht
        (bis zur Rechnungsnummer je Auftragsposition). Die
        Rechnungen unter "rechnungen" im Projekt haben eigene Preise und
        keinen solchen Bezug.

        Ausgewählt wird über ein Zeitfenster: "stunden_vor_tagen": [von, bis]
        nimmt alle noch offenen, abrechenbaren Zeilen des Projekts aus diesen
        Tagen. "einkauf" nennt Eingangsrechnungen über ihre Nummer; ihre
        Fremdleistungen zu diesem Projekt gehen mit. Leistungsdatum und
        -zeitraum kommen aus den Tagen der Zeilen. "entwurf": true lässt die
        Rechnung als Entwurf stehen; die Zeilen gelten dann als reserviert.
        """
        for e in eintraege:
            projekt = self.projekt(e['projekt'])
            zeilen = Erfassungszeile.objects.none()
            if 'stunden_vor_tagen' in e:
                von, bis = e['stunden_vor_tagen']
                zeilen = Erfassungszeile.objects.filter(
                    projekt=projekt, abrechenbar=True,
                    abgerechnet_in__isnull=True,
                    datum__range=(self.heute - timedelta(days=von),
                                  self.heute - timedelta(days=bis)))
            fremd = Fremdleistung.objects.filter(
                projekt=projekt, rechnung__nummer__in=e.get('einkauf', []),
                abgerechnet_in__isnull=True)
            if not zeilen.exists() and not fremd.exists():
                abbruch(f'{projekt.nummer}: Abrechnung ohne Inhalt - im '
                        f'Zeitfenster {e.get("stunden_vor_tagen")} liegt '
                        f'nichts Offenes, und "einkauf" trifft nichts.')

            tage = sorted(zeilen.values_list('datum', flat=True))
            beleg, _ = in_rechnung_uebernehmen(zeilen=zeilen,
                                               fremdleistungen=fremd)
            if tage:
                beleg.leistungsdatum, beleg.leistungsdatum_bis = (tage[0],
                                                                  tage[-1])
            if 'betreff' in e:
                beleg.betreff = self.jahr(e['betreff']).replace(
                    '{nummer}', projekt.nummer)
            beleg.save()
            if not e.get('entwurf'):
                self.festschreiben(beleg, self.tage_zurueck(e))

    def mahnungen(self, eintraege):
        """Zahlungserinnerungen zu bereits gestellten Rechnungen.

        Ohne sie zeigt die Startseite unter "Gemahnt" eine Null, und der
        ganze Weg vom Zahlungsziel zur Mahnstufe bliebe unbelegt.

        "zu": "aelteste" ist der einzige Sonderwert im ganzen Format -
        gemeint ist die älteste festgeschriebene Rechnung. Welche das ist,
        ergibt sich aus dem Bestand und soll sich mit ihm ändern dürfen;
        ein Verweis über den Betreff wäre hier die schlechtere Wahl.
        """
        for e in eintraege:
            if 'zu_beleg' in e:
                # Der klare Fall: Im Bestand steht, welche Rechnung gemahnt
                # wird. Das ist die bessere Wahl, sobald es darauf ankommt -
                # etwa wenn die gemahnte Summe auf der Startseite stehen
                # soll, ohne wie ein Betrieb in Schieflage auszusehen.
                betreff = self.jahr(e['zu_beleg'])
                beleg = Beleg.objects.filter(
                    typ=BelegTyp.RECHNUNG, betreff=betreff).first()
                if beleg is None:
                    abbruch(f'Mahnung: Keine Rechnung mit dem Betreff '
                            f'"{betreff}".')
            elif e.get('zu') == 'aelteste':
                beleg = (Beleg.objects
                         .filter(typ=BelegTyp.RECHNUNG)
                         .exclude(nummer='')
                         .order_by('belegdatum')
                         .first())
                if beleg is None:
                    abbruch('Mahnung: Es gibt keine festgeschriebene '
                            'Rechnung, die sich mahnen liesse.')
            else:
                abbruch('Mahnung: Entweder "zu_beleg" mit dem Betreff der '
                        'Rechnung oder "zu": "aelteste".')
            mahnung = faktura_services.mahnung_erstellen(
                beleg_id=beleg.pk, stufe=e.get('stufe', 1))
            self.festschreiben(mahnung, self.tage_zurueck(e))

    def festschreiben(self, beleg, tage):
        """Schreibt fest, mit einem Belegdatum in der Vergangenheit.

        **Beim Festschreiben und nicht danach.** Wer das Datum hinterher am
        unveränderlichen Beleg vorbei setzt, bekommt drei Fehler auf einmal,
        die man erst im PDF sieht: Das Dokument trägt den heutigen Tag, das
        Zahlungsziel rechnet ab heute (die Rechnung von vor sechs Wochen ist
        nie überfällig), und die Nummer kommt aus dem Kreis des laufenden
        Jahres statt aus dem des Belegjahres.
        """
        return faktura_services.beleg_festschreiben(
            beleg_id=beleg.pk,
            belegdatum=self.heute - timedelta(days=tage),
        )

    # -- Nachschlagen, immer über Namen -------------------------------------

    def kunde(self, name):
        if name not in self.kunden:
            abbruch(f'Kunde "{name}" steht in keiner Kundendatei. '
                    f'Bekannt: {", ".join(sorted(self.kunden)) or "(keiner)"}.')
        return self.kunden[name]

    def leistung(self, bezeichnung):
        if bezeichnung not in self.katalog:
            abbruch(f'Leistung "{bezeichnung}" steht nicht im Katalog. '
                    f'Bekannt: {", ".join(sorted(self.katalog)) or "(keine)"}.')
        return self.katalog[bezeichnung]

    @staticmethod
    def positionen(beleg, auftrag):
        """Die Positionen eines Belegs, eigene oder die des Auftrags.

        ``"positionen_aus_auftrag": true`` übernimmt sie samt Verknüpfung:
        So entsteht die Schlussrechnung eines abgeschlossenen Vorhabens,
        das seine Leistung einmal komplett abrechnet. Das spart, dieselben
        Positionen zweimal in die Datei zu schreiben; bei vierundzwanzig
        Vorhaben ist das der Unterschied zwischen lesbar und nicht.

        Ohne Verknüpfung zeigte die Auftragsakte bei jedem voll berechneten
        Vorhaben "0 von 120 Std abgerechnet".
        """
        if not beleg.get('positionen_aus_auftrag'):
            return beleg['positionen']
        if auftrag is None:
            abbruch('"positionen_aus_auftrag" ohne Auftrag am Vorhaben.')
        return [{'leistung': p.bezeichnung, 'menge': str(p.menge),
                 'preis': str(p.einzelpreis), 'einheit': p.einheit,
                 'auftragsposition': p}
                for p in auftrag.positionen.all()]

    def lieferant(self, name):
        if name not in self.lieferanten:
            abbruch(f'Lieferant "{name}" steht in keiner Lieferantendatei. '
                    f'Bekannt: '
                    f'{", ".join(sorted(self.lieferanten)) or "(keiner)"}.')
        return self.lieferanten[name]

    def projekt(self, nummer):
        nummer = self.jahr(nummer)
        if nummer not in self.projekte:
            abbruch(f'Projekt "{nummer}" gibt es nicht. '
                    f'Bekannt: {", ".join(sorted(self.projekte)) or "(keins)"}.')
        return self.projekte[nummer]

    def einheit_aus_katalog(self, bezeichnung):
        aus_katalog = self.katalog.get(bezeichnung)
        return aus_katalog.einheit if aus_katalog else 'Stk'

    def person(self, anmeldename):
        if anmeldename not in self.leute:
            abbruch(f'Person "{anmeldename}" steht in keiner '
                    f'Mannschaftsdatei. '
                    f'Bekannt: {", ".join(sorted(self.leute)) or "(keine)"}.')
        return self.leute[anmeldename]

    @staticmethod
    def auftrag_von(projekt):
        """Der festgeschriebene Auftrag des Projekts, der erste, wenn es
        mehrere gibt; None ohne Auftrag."""
        return (Beleg.objects
                .filter(projekt=projekt, typ=BelegTyp.AUFTRAG,
                        status=BelegStatus.FESTGESCHRIEBEN)
                .order_by('pk').first())

    @staticmethod
    def auftragsposition(auftrag, bezeichnung):
        """Die Auftragsposition dieser Leistung oder None.

        None ohne Auftrag und bei einer Leistung, die nicht beauftragt
        wurde: Dann bucht der Aufrufer über den Katalog, und genau das soll
        in einem Bestand vorkommen, weil die Gruppe "Ohne Auftrag" in der
        Erfassungsmaske sonst nie belegt wäre.
        """
        if auftrag is None:
            return None
        return auftrag.positionen.filter(bezeichnung=bezeichnung).first()

    def art(self, bezeichnung, einheit):
        aus_katalog = self.katalog.get(bezeichnung)
        if aus_katalog:
            return aus_katalog.art
        return ART_JE_EINHEIT.get(
            (einheit or '').strip().lower(), Leistungsart.MENGE)

    # -- Datumsangaben, immer relativ zu heute -------------------------------

    def tage_zurueck(self, angaben):
        """vor_tagen oder vor_monaten, genau eines von beiden.

        Über die Monatszahl gerechnet und nicht über 30 Tage: Nur so landet
        jeder Beleg in genau einem Monat des Verlaufs, und keiner rutscht
        über eine Monatsgrenze.
        """
        if 'vor_tagen' in angaben:
            return int(angaben['vor_tagen'])
        if 'vor_monaten' in angaben:
            return (self.heute - self.monate(int(angaben['vor_monaten']))).days
        abbruch('Angabe ohne Datum: "vor_tagen" oder "vor_monaten" fehlt.')

    def projektnummer(self, angaben):
        """Die Nummer eines Vorhabens, mit dem Jahr, in das es gehört.

        **Wozu ``jahr_vor_tagen``.** Ein abgeschlossenes Vorhaben von vor
        elf Monaten trägt eine Nummer aus dem Jahr, in dem es lief, nicht
        aus dem, in dem der Bestand eingespielt wird. Ohne die Angabe hieße
        es "2026-101" und trüge eine Schlussrechnung vom Oktober 2025; im
        Termin fragt jemand nach.

        Die Angabe ist die Zahl der Tage bis zu dem Tag, aus dem die
        Jahreszahl kommen soll, meist derselbe Wert wie beim Abschluss.
        Ohne sie gilt das laufende Jahr, und das ist für alles Laufende
        richtig.
        """
        nummer = angaben['nummer']
        if 'jahr_vor_tagen' in angaben:
            tag = self.heute - timedelta(days=int(angaben['jahr_vor_tagen']))
            return nummer.replace('{jahr}', str(tag.year))
        return self.jahr(nummer)

    def jahr(self, text):
        """Ersetzt {jahr} und {vorjahr} durch die Jahreszahl.

        Gebraucht in Projektnummern und überall dort, wo eine Datei auf
        eine verweist: "{jahr}-014" muss beim Anlegen und beim Nachschlagen
        dasselbe ergeben.

        **{vorjahr} gibt es für abgeschlossene Vorhaben**, die über den
        Jahreswechsel liefen. Ohne den Platzhalter trägt ein Vorhaben von
        vor zehn Monaten die Nummer des laufenden Jahres, und im Termin
        fragt jemand nach.
        """
        # Erst die Vorlagen bekannter Vorhaben: "{jahr}-101" mit
        # jahr_vor_tagen heisst vielleicht "2025-101", und ein Verweis aus
        # einer späteren Datei muss dieselbe Nummer treffen, nicht die
        # des laufenden Jahres.
        for vorlage, nummer in self.nummern.items():
            text = text.replace(vorlage, nummer)
        return (text.replace('{jahr}', str(self.heute.year))
                    .replace('{vorjahr}', str(self.heute.year - 1)))

    def monate(self, monate):
        # Der Tag wird auf höchstens 28 gedeckelt; den 31. gibt es nicht in
        # jedem Monat.
        gesamt = self.heute.year * 12 + (self.heute.month - 1) - monate
        return date(gesamt // 12, gesamt % 12 + 1, min(self.heute.day, 28))


# -- Los ---------------------------------------------------------------------

# Dieselbe Sperre wie früher in den Seed-Befehlen und aus demselben Grund:
# Der Lader schreibt Belege fest und zieht dabei echte Nummern aus dem
# lückenlosen Kreis. Auf einer produktiven Anlage risse ein versehentlicher
# Aufruf Lücken, die sich einem Prüfer nicht erklären lassen.
if not (settings.DEBUG or settings.FAKTURA_DEMODATEN_ERLAUBT):
    abbruch(
        'Diese Installation nimmt keine Demodaten an. Der Lader schreibt '
        'Belege fest und zieht dabei echte Nummern aus dem lueckenlosen '
        'Kreis. Fuer eine Test- oder Vorfuehrinstallation '
        'FAKTURA_DEMODATEN_ERLAUBT=True setzen (in .env.app), auf einer '
        'produktiven Anlage nicht.')

with open(BUENDEL, encoding='utf-8') as f:
    dateien = json.load(f)

with transaction.atomic():
    Lader().alles(dateien)

print(f'\nBestand eingelesen: {len(dateien)} Datei(en).')
