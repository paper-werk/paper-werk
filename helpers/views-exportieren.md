# Gespeicherte Ansicht aus Paperless in die JSON übernehmen

Du hast in Paperless eine Ansicht gebaut und willst sie ins Starterpaket
(`saved_views.json`) übernehmen. Das Python-Skript `views_exportieren.py` liest sie
aus und gibt den fertigen Eintrag aus, mit Namen statt IDs.

Es ist rein lesend: Es ändert weder die Instanz noch eine Datei. Die Ausgabe
geht nur ans Terminal.

## Zwei Wege

Die Quelle ist immer die API von Paperless: `https://localhost:8005/api/saved_views/8/`
liefert die Ansicht 8 mit allen Feldern. `https://localhost:8005/` ist dabei
die jeweilige Installation (Adresse und Port hängen vom Projekt ab).

- **Nachlesen:** Die Adresse im angemeldeten Browser öffnen und die Felder von
  Hand übernehmen. Die Werte in `filter_rules` sind dort IDs von Tags,
  Dokumenttypen usw., die du selbst in Namen übersetzen musst.
- **Mit dem Skript:** Es holt dasselbe aus der API und gibt es gleich in der
  Form aus, die `saved_views.json` braucht (Namen statt IDs). Das ist der
  bequemere Weg und der, der unten beschrieben ist.

## Schritte

1. **ID der Ansicht ablesen.** Ansicht in Paperless öffnen, die Zahl am Ende
   der Adresse ist die ID: `https://localhost:8005/view/8` → `8`.
2. **Skript ausführen** (aus der Repo-Wurzel, in jedem Terminal, Python 3 genügt, nichts zu installieren):

   ```bash
   python helpers/views_exportieren.py dev 8
   ```

   `dev` ist der Name der Installation wie bei `./stack.sh`, `config` steht
   für `config/`. Das Skript nimmt
   Container und Token aus dessen `einstellungen/setup.conf`.
3. **Ausgabe in die `saved_views.json`** des Projekts einfügen (als weiteres
   Element im Array), z. B.
   `config-repos/paper-werk-config-dev/einstellungen/paperless/starterpaket/saved_views.json`.
4. Committen. Der Diff zeigt, was neu ist.

## Was du wissen musst

- **`show_in_sidebar`** gehört seit Paperless 3.x nicht zur Ansicht, sondern zu
  den UI-Einstellungen des Nutzers. Das Skript liest es von dort (Nutzer des
  Tokens in der `setup.conf`), es steht also so, wie deine Seitenleiste gerade
  aussieht.
- **Namen statt IDs:** Tags, Dokumenttypen, Korrespondenten, Speicherpfade und
  Custom Fields werden in Namen übersetzt. `apply.sh` löst sie beim Einspielen
  wieder auf. Die Namen müssen im Starterpaket vorkommen, sonst bricht das
  Einspielen mit „Unbekannt (…)" ab.
- **Regeltyp 42** (Custom-Field-Abfrage) bleibt roh, die Feld-ID steckt in
  einem JSON-String. Solche Ansichten brauchen nach dem Einspielen eine
  Korrektur in der Oberfläche.
- **`_kommentar`** legt das Skript nicht an. Wer möchte, ergänzt ihn von Hand.
  Bei „alle Ansichten“ (siehe unten) gehen deshalb die Kommentare der
  bestehenden Datei verloren, wenn du sie einfach ersetzt.
- Die **Reihenfolge** in der Seitenleiste kommt nicht mit.

## Wenn es nicht läuft

- Läuft der Stack, und stimmt
  `PAPERLESS_CONTAINER` in der `setup.conf`?
- „setup.conf nicht gefunden": Projektname falsch geschrieben.
- „Abruf gescheitert": Stack läuft nicht, oder der Token in der `setup.conf` ist nach einem Neuaufsetzen ungültig.

## Alle Ansichten auf einmal

Ohne Ansicht-ID gibt das Skript alle Ansichten als Array aus, im Format der
ganzen `saved_views.json`:

```bash
python helpers/views_exportieren.py dev
```

Die Ausgabe erscheint nur im Terminal. Willst du sie ins Starterpaket
übernehmen, kopierst du sie selbst in die Datei (oder leitest sie mit `>` um).
Der git-Diff zeigt dir danach, was sich gegenüber dem Starterpaket geändert
hat.
