# Skriptgesteuerte Erstinstallation (Rahmengerüst)

**Komplette Neuinstallation von null auf einem Kundenrechner?** → Die volle
Schritt-für-Schritt-Anleitung (inkl. Voraussetzungen, Stack starten) steht in
[../Kundeninstallation.md](../Kundeninstallation.md). Dieses README hier
dokumentiert nur die Setup-Skripte selbst (Schritt 5 dort).

Ziel: Nach `./paper-werk up <name>` eines Projekt-Stacks (in `config/` oder `config-repos/paper-werk-config-<name>/`,
siehe [../README.md](../README.md)) soll ein Kunde nicht mit nackten Systemen
dastehen. Diese Skripte spielen reproduzierbar die Grundkonfiguration ein.

Die Skripte selbst sind projektunabhängig (ein Satz für alle Installationen);
`setup.conf`, `n8n/credentials.json`, `n8n/workflows.list`,
`paperless/starterpaket/*.json` und `kopia/ignore.rules` werden dafür nicht
hier, sondern im jeweiligen Projektordner unter `<projekt>/einstellungen/` erwartet
(per `--project <projektordner>` angegeben):

Neben den Modulen liegen hier zwei Skripte, die keine sind, weil sie nichts
einspielen:

| Skript | Was es tut |
| --- | --- |
| `doktor.sh <installation>` | Zustandsbericht: Stand, Änderungen an ausgelieferten Dateien, `.env`-Abgleich, Container, Zertifikat |
| `aktualisieren.sh <installation>` | Update in einem Befehl: prüfen, sichern, `git pull`, bauen, hochfahren, nachsehen |

| Modul | Was passiert |
| --- | --- |
| `app/` | **paper-werk-app startklar machen**: ersten Superuser anlegen (Django legt von sich aus keinen an), den Gruppen `paper-werk-buero`, `paper-werk-projektleitung` und „Faktura Dienst" ihre Rechte geben, Dienstzugang für n8n samt Schlüssel einrichten |
| `paperless/` | Starterpaket einspielen: Tags, Dokumenttypen, Custom Fields, Speicherpfade, Korrespondenten, Arbeitsabläufe und gespeicherte Ansichten (aus `paperless/starterpaket/*.json`) |
| `n8n/` | Optional Credentials aus `n8n/credentials.json` importieren, dann die in `n8n/workflows.list` gelisteten Workflow-JSONs (aus dem Repo-Ordner `n8n/`) importieren und aktivieren |
| `sso/` | **Nur mit Anmeldung über Microsoft, nicht im Standardlauf**: in Paperless die Gruppen `paper-werk-buero` und `paper-werk-projektleitung` anlegen, ihnen das Archiv freigeben und einen Workflow einrichten, der jedes neue Dokument freigibt (siehe `sso/apply.sh` und `Kundeninstallation.md`, Abschnitt 7.5) |
| `kopia/` | Repository anlegen/verbinden (externe Disk oder Backblaze B2), Default-Policy (Ignores, zstd, täglicher Snapshot) setzen, ersten Snapshot ziehen |

## Verwendung

Auf dem Docker-Host (nicht auf dem Entwicklungsrechner), laufender Stack
vorausgesetzt. Die Vorlagen für die Werte liegen in
[../config-template/einstellungen/](../config-template/einstellungen/); in den
Installationsordner kopieren und die `.example`-Dateien ausfüllen (siehe [../Kundeninstallation.md](../Kundeninstallation.md),
Schritt 5).

```bash
cd setup
bash setup.sh --project ../config              # alle Module
bash setup.sh --project ../config app          # nur paper-werk-app
bash setup.sh --project ../config paperless    # oder gezielt einzelne: app | paperless | n8n | kopia
bash setup.sh --project ../config n8n --force  # vorhandene n8n-Workflows überschreiben (siehe unten)
```

**Auf Windows in Git Bash ausführen**, nicht in PowerShell/cmd. Dort ist
`.sh` kein ausführbarer Dateityp und Windows öffnet stattdessen den
„Womit öffnen?"-Dialog. `bash setup.sh` statt `./setup.sh` funktioniert
zusätzlich ohne gesetztes Unix-Ausführungsrecht (siehe Troubleshooting in
[../Kundeninstallation.md](../Kundeninstallation.md#troubleshooting)).

**n8n-Workflows werden standardmäßig nicht überschrieben:** Existiert ein
Workflow (gleiche ID) in n8n schon, wird er übersprungen; sonst gingen
Änderungen verloren, die jemand direkt in der n8n-UI gemacht hat
(Credentials, Aktivierung, Node-Anpassungen). Mit `--force` wird trotzdem
überschrieben.

`setup.conf` (im Projektordner unter `einstellungen/`) enthält Secrets und ist
gitignored; nur das `.example` wird versioniert.

Benötigt auf dem Host: `bash`, `docker`, `curl`, `jq`.

## Wie die Inhalte gepflegt werden

- **paper-werk-app**: Hier gibt es keine Seed-Dateien, nur Werte in
  `setup.conf`: `APP_ADMIN_USER`/`_PASSWORD`/`_EMAIL` und `APP_DIENSTZUGANG`.
  Das ist Absicht: Die Rechteliste der Gruppen steht im Quelltext der App neben
  den Modellen, zu denen sie gehört (`faktura/management/commands/faktura_rechte.py`).
  Eine zweite Liste hier würde beim nächsten neuen Modell vergessen.

  **Der Superuser wird nur beim Anlegen angefasst.** Existiert er, lässt das
  Modul ihn unverändert und rührt insbesondere sein Passwort nicht an. Sonst
  wäre jeder wiederholte Setup-Lauf eine stille Rücksetzung des
  Administratorkontos, und `setup.sh` ohne Modulangabe lässt *alle* Module
  laufen, also auch dieses. Geprüft: Nach einem zweiten Lauf meldet sich der
  Benutzer weiterhin mit seinem geänderten Passwort an.

  **Der Dienstzugang** (`APP_DIENSTZUGANG`, ausgeliefert als `n8n`) ist das
  Gegenstück zum `PAPERLESS_TOKEN`: ein Konto ohne Passwort und ohne
  Admin-Zugang, das sich nur über seinen Schlüssel ausweist. Das Modul gibt
  den Schlüssel aus; er gehört danach in die n8n-Credential. Leer lassen
  überspringt den Schritt.

- **Paperless-Starterpaket**: JSON-Dateien in `paperless/starterpaket/` sind
  die einzige Quelle; dort Objekte ergänzen, nicht im Skript. In
  `workflows.json` werden Tags, Dokumenttypen, Speicherpfade, Custom Fields,
  Korrespondenten, Nutzer und Gruppen per **Name** referenziert, das Skript löst
  sie in die IDs der Zielinstanz auf (Regeln in
  [paperless/resolve-workflow.jq](paperless/resolve-workflow.jq), ausgelagert
  damit sie ohne laufende Instanz testbar sind). Aufgelöst wird nur, was als
  String dasteht. Rohe Zahlen gehen unverändert durch, ältere
  `workflows.json` funktionieren also weiter.
  `storage_paths.json` wird wie Tags/Dokumenttypen
  1:1 angelegt (keine Namensauflösung nötig). Der Pfad selbst kann per
  Jinja2-Template (`{{ created_year }}`, `{{ title }}`, `{{ document_type }}`,
  `{{ custom_fields | get_cf_value(...) }}`, …) auf andere Starterpaket-Objekte
  verweisen, das ist reine Paperless-Laufzeitauswertung.

  Zwei Dinge löst das Skript bewusst **nicht** auf:
  - `filter_custom_field_query`: Dort steckt die Feld-ID in einem
    serialisierten JSON-String, nicht in einem eigenen Feld. Solche Abläufe
    brauchen nach dem Einspielen eine Korrektur in der Paperless-Oberfläche.
  - **Nutzer und Gruppen** werden per Name aufgelöst, aber nicht angelegt;
    Paperless kennt dafür keinen Seed-Endpunkt. Sie müssen vorher existieren,
    sonst bricht der Lauf mit `Unbekannt (Nutzer): …` ab. Nur relevant für
    Installationen mit Mehrbenutzerbetrieb (`assign_owner`,
    `assign_view_groups`, …).

  **Jede Seed-Datei ist optional.** Fehlt sie, wird der Schritt mit einer
  Meldung übersprungen. Ältere Projektordner ohne `correspondents.json` oder
  `saved_views.json` laufen also unverändert weiter.
- **Gespeicherte Ansichten** (`saved_views.json`): dasselbe Prinzip, aber der
  Bezug steckt nicht im Feldnamen. Eine Filterregel ist immer nur
  `{"rule_type": N, "value": "…"}`, und erst der Regeltyp verrät, ob der Wert
  ein Tag, ein Dokumenttyp oder schlicht ein Suchbegriff ist. Welcher Typ auf
  welche Objektart zeigt, steht in
  [paperless/resolve-saved-view.jq](paperless/resolve-saved-view.jq); alles
  andere geht unverändert durch. Ohne `owner` ordnet die API die Ansicht dem
  Token-Inhaber aus `setup.conf` zu. Für Einzelplatz-Installationen ist das
  richtig; sonst den Benutzernamen eintragen, er wird aufgelöst. Regeltyp 42
  („custom fields query") bleibt aus demselben Grund wie
  `filter_custom_field_query` unaufgelöst.
- **n8n-Workflows**: Die Workflow-JSONs selbst liegen wie bisher versioniert
  unter `n8n/` (Repo-Wurzel). `n8n/workflows.list` bestimmt nur, *welche*
  davon eine Erstinstallation bekommt und ob sie aktiviert werden. Die
  Trennlinie dabei: **Webhook-Workflows ohne Mailversand werden aktiv
  ausgeliefert** (`;true`), alles mit einem Mail-Node bleibt `;false`. Ein
  Webhook-Workflow tut von sich aus nichts: Er wartet auf den Aufruf eines
  Paperless-Arbeitsablaufs, der wiederum an einem bewusst gesetzten Tag hängt.
  Inaktiv beantwortet er den Aufruf mit 404, was nur im Paperless-Log landet;
  aktiv mit noch fehlendem API-Key schlägt er sichtbar in der
  n8n-Ausführungsliste fehl. Mail-Workflows dagegen hängen sechsmal an einem
  Zeitplan und laufen los, sobald sie aktiv sind, also bevor jemand
  geprüft hat, ob in `pw_config` die richtigen Adressen stehen und ob die
  SMTP-Credential trägt. Die `enabled`-Flags in `workflows.json` sind auf
  dieselbe Trennlinie gesetzt.
  Kommentare in `workflows.list` gehören auf eine **eigene Zeile**: das Skript
  liest alles nach dem `;` als Aktivierungsflag, ein angehängtes `# …` würde
  ein `;true` unbemerkt entwerten.
- **Kopia-Ignores**: `kopia/ignore.rules` (Syntax wie `.gitignore`), Werte aus
  dem erprobten Setup in `docs/kopia-backblaze.md`.
- **n8n-Credentials**: `n8n/credentials.json` (gitignored, aus
  `credentials.json.example` kopieren und ausfüllen), optional, aber
  empfohlen. IDs darin sind bewusst fest und passen zu den
  `credentials`-Referenzen, die die Workflow-Dateien in `n8n/` bereits
  enthalten (geprüft: alle Workflows aus `workflows.list.example`
  referenzieren konsistent dieselben drei IDs für "Header Auth paperless",
  "Header Auth Mistral", "SMTP account". Einige *nicht* gelistete Workflows
  in `n8n/` nutzen dagegen weitere, hier nicht ausgelieferte Credential-IDs
  und brauchen nach einem manuellen Import Nacharbeit in der UI). Dadurch
  ist die Credential nach dem Import automatisch im jeweiligen Node
  vorausgewählt, ohne Nachziehen in der n8n-UI. Gleiche
  Idempotenz wie bei Workflows: vorhandene ID wird übersprungen, `--force`
  überschreibt (z. B. um ein rotiertes Token nachzuziehen). Ohne die Datei
  wird dieser Schritt übersprungen; Workflows lassen sich dann wie
  bisher manuell in der UI verdrahten.
- **Instanz-Einstellungen**: `n8n/config.json` (versioniert, aus
  `config.json.example` kopieren und ausfüllen; **keine Geheimnisse**, die
  gehören in `credentials.json`): die Adressen und URLs dieser
  Installation. Siehe nächster Abschnitt.

## Instanz-Einstellungen: die Data Table `pw_config`

**Alle** Adressen und URLs einer Installation stehen an genau einer Stelle: in
der n8n-Data-Table `pw_config`, einer Tabelle mit den Spalten `key`,
`value` und `hint`. In den Workflow-JSONs steht keine einzige Mail-Adresse
mehr.

Vorher lagen sie in jedem Workflow im Node „Konfiguration“: dieselbe
Betreiber-Adresse in zehn Workflows, unter fünf verschiedenen Namen
(`empfaenger_email`, `report_email`, `alarm_email`, `fallback_email`,
`admin_email`). Eine Installation anzupassen hieß, ein Dutzend Workflows in der
n8n-Oberfläche zu öffnen und in jedem JavaScript zu editieren. Genau die eine
Stelle zu übersehen, die es auch noch brauchte, war der Normalfall.

### Wie es jetzt aussieht

Jeder Workflow hat zwei Knoten statt einem:

```text
[Trigger] → [Instanz-Einstellungen] → [Konfiguration] → …
            Data-Table-Knoten,        Code-Knoten: faltet die Zeilen zu
            liest alle Zeilen         einem Objekt und ergänzt die
            aus pw_config             FACHLICHEN Werte dieses Workflows
```

Die Trennlinie: **in `pw_config` steht, was für die ganze Anlage gilt**
(Adressen, URLs, Instanzname), **im Konfigurations-Node steht, was zu diesem
einen Workflow gehört** (`nachfass_tage: 14`, `vorlauf_tage: 90`, Tag-Namen,
Custom-Field-Namen). Ein Wert, den zwei Workflows brauchen, gehört in die
Tabelle, etwa `mail_duo`, das der Monatslauf und der Sofortversand
gleichermaßen brauchen.

Der Konfigurations-Node gibt weiterhin dieselben Schlüssel aus wie vorher
(`empfaenger_email`, `absender`, …). Die nachgelagerten Knoten mussten deshalb
nicht angefasst werden; sie sehen keinen Unterschied. Nur die Herkunft der
Werte hat sich geändert:

```js
const pw = (key) => { /* … aus der Tabelle, wirft wenn leer … */ };

return [{ json: {
  // ── aus der Data Table pw_config ──
  paperless_url:    pw('paperless_url'),
  empfaenger_email: pw('mail_betrieb'),
  absender:         pw('mail_absender'),

  // ── fachlich, hier zu pflegen ──
  tag_angebot: 'angebot-offen',
  nachfass_tage: 14
}}];
```

### Pflege

**Im Browser**: n8n-Oberfläche → Data Tables → `pw_config`. Änderungen wirken
sofort, ohne Neustart und ohne Workflow-Import. Die Spalte `hint` steht
direkt neben dem Wert und erklärt, was gemeint ist. Deshalb passt eine
Tabelle hier besser als Umgebungsvariablen.

**Beim Setup**: `n8n/apply.sh` spielt `config.json` ein. Dafür importiert und
veröffentlicht es den Workflow `n8n/config-tabelle-schreiben.json`, schickt ihm
die Zeilen per Webhook und nimmt ihn danach wieder vom Netz
(`n8n unpublish:workflow`). Ein dauerhaft offener Webhook, der die
Betriebsadressen umschreiben kann, hat auf einer Kundeninstallation nichts
verloren. Beides ist idempotent: die Tabelle wird per `createIfNotExists`
wiederverwendet, die Zeilen per Upsert auf die Spalte `key` geschrieben. Zeilen,
die nur in der Tabelle stehen, bleiben unangetastet; der Seeder löscht nie.

Leere Werte sind erlaubt und gewollt: die Tabelle wird mit allen Zeilen
ausgeliefert, auch den unausgefüllten, damit im Browser sichtbar ist, *was
noch fehlt*. `apply.sh` nennt sie am Ende als Warnung. Gemeckert wird erst beim
Lesen, im Konfigurations-Node des Workflows, der den Wert tatsächlich braucht:

> Der Schlüssel "mail_duo" steht in der Data Table "pw_config", hat aber noch
> keinen Wert. In der n8n-Oberfläche unter "Data Tables" eintragen.

### Was beim Bauen zu beachten ist

- **Data Tables sind kein Enterprise-Feature.** Das Modul `data-table` steht in
  n8n 2.32.7 in den `defaultModules` und trägt kein `.ee`-Suffix. Es ist ab
  Werk aktiv, ohne Lizenz und ohne Umgebungsvariable.
- **`n8n execute` per CLI lädt die Module nicht.** Ein Workflow mit
  Data-Table-Knoten bricht dort mit `Attempted to use Data table node but the
  module is disabled` ab. Das betrifft nur das Testen über die CLI; der
  laufende Server ist davon nicht berührt. Zum Testen deshalb über den Webhook
  gehen, nicht über `n8n execute`.
- **Die Tabelle wird per NAME referenziert**, nicht per ID (der Data-Table-Knoten
  kann beides). Sonst stünde in den versionierten Workflow-JSONs eine ID, die
  nur auf genau einer Instanz existiert.
- **`/healthz` antwortet `ok`, bevor die Webhooks registriert sind**; der
  erste Aufruf läuft dann mehrere Sekunden in einen 404.
  `apply.sh` wartet deshalb auf den Webhook selbst, nicht auf `healthz`.
- **Wer den Webhook-Body im Konfigurations-Node braucht, muss ihn über
  `$('Webhook')` holen.** `$input` sind dort jetzt die Tabellenzeilen. Betrifft
  `objektakte-export` und `projektakte-export`, die ihre Aufrufparameter mit
  den Einstellungen zusammenführen.
- **Der Error-Workflow kann die Tabelle lesen.** Ein Lauf im `mode: error`
  liest die Data Table wie jeder andere. Fehlt die
  Tabelle allerdings, bricht `fehler-melden` selbst ab, und das verschluckt n8n
  kommentarlos. Der Test mit `fehler-melden-test.json` ist damit noch wichtiger
  als vorher.

### Bestehende Installationen nachziehen

Ältere Instanzen haben Workflows mit Adressen im Konfigurations-Node. Ohne
`--force` bleiben sie unverändert, weil `apply.sh` vorhandene IDs
überspringt. Umstellen:

1. `einstellungen/n8n/config.json` im Projektordner anlegen (aus
   `config-template/einstellungen/n8n/config.json.example`) und die Werte eintragen, die
   auf dieser Instanz gelten, etwa `instanz: buero-nord`.
2. `bash setup.sh --project ../config n8n --force`

Reihenfolge ist wichtig: `--force` ohne gefüllte `config.json` überschreibt die
Workflows mit Fassungen, die eine leere Tabelle lesen; die brechen dann mit
der Meldung oben ab. Kaputt geht dabei nichts, aber bis die Tabelle steht,
läuft auch nichts.

Umgekehrt ist der Weg gefahrlos: `config.json` anlegen und `apply.sh` **ohne**
`--force` laufen lassen füllt nur die Tabelle und lässt die Workflows in Ruhe.
Die Tabelle stört die alten Workflows nicht, weil sie sie nicht lesen.

#### Wenn die IDs auseinanderlaufen

Auf einer Instanz, die über die n8n-Oberfläche gewachsen ist, tragen die
Workflows andere IDs als die Repo-Dateien. `--force` erzeugt dort keine
Updates, sondern Duplikate (oder überschreibt einen fremden Workflow, der
zufällig auf einer Repo-ID sitzt).

Für solche Instanzen gibt es einen Weg, der die Repo-Dateien gar nicht erst
importiert:

1. `docker exec -u node <n8n> n8n export:workflow --all --output=…`. Der
   Export ist zugleich der Rückfallpunkt.
2. Aus dem Export die betroffenen Workflows als Einzeldateien ziehen.
3. **Nur den Konfigurationsteil tauschen**: den Knoten `Instanz-Einstellungen`
   und den `jsCode` von `Konfiguration` aus der Repo-Fassung übernehmen, die
   Verdrahtung umhängen, die harten Paperless-URLs in den HTTP-Knoten durch
   `{{ $('Konfiguration').first().json.paperless_url }}` ersetzen. Alles
   andere (ID, Credentials, Webhook-Pfade, `settings.errorWorkflow`, lokale
   Abweichungen in anderen Knoten) bleibt unberührt.

   **Dabei nach ALLEN Hosts suchen, nicht nur nach den bekannten.** Auf einer
   gewachsenen Instanz stehen mehrere Adressen für dasselbe Paperless
   nebeneinander, etwa `http://webserver:8000` *und*
   `http://paperless.lan`. Wer nur nach dem Docker-Servicenamen sucht,
   übersieht die zweite Sorte und lässt eine harte URL stehen. Der Griff, der
   es findet:

   ```bash
   jq -r '.[] | .name as $w | .nodes[]
          | select(.type != "n8n-nodes-base.stickyNote")
          | "\($w)\t\(.name)\t\(.parameters|tostring)"' export.json \
     | grep -oP 'https?://[a-zA-Z0-9._:-]+' | sort -u
   ```

4. Zurückspielen mit `import:workflow`, danach `publish:workflow` für jeden,
   der vorher aktiv war (der Import setzt `active` auf false zurück).
5. Container neu starten.

Prüfen lässt sich das Ergebnis ohne Nebenwirkungen, indem man einen
Webhook-Workflow mit einer **nicht existierenden** Dokument-ID aufruft: die
beiden Konfigurationsknoten laufen dann vollständig durch, der Abbruch kommt
erst beim HTTP-Aufruf mit einem 404. Steht in der Fehlermeldung die richtige
URL, hat die Tabelle getragen. Als Zugabe löst der Fehlschlag `fehler-melden`
aus, und wenn dessen Lauf auf `success` steht, ist auch der Error-Pfad
verifiziert.

## Konvention: Paperless löst aus, n8n entscheidet

Das Muster ist zuerst in `handschrift-ocr-titel-mistral` umgesetzt.

Es ersetzt eine Absprache zwischen Paperless und n8n über Reihenfolge und
Tag-Wechsel. Eine solche Absprache bricht, sobald ein Beteiligter sich anders
verhält, und der Kunde kann in der Paperless-Oberfläche jederzeit einen
Auslöser hinzufügen.

Die Regel lautet deshalb:

> **Paperless ruft nur den Webhook mit `doc_url` auf. Sonst nichts.** Keine
> `remove_tags`-Aktion, keine Mitwirkung. Ob etwas zu tun ist, entscheidet
> allein n8n, anhand des Dokumentzustands, den es ohnehin liest.

### Der Aufbau

```text
Webhook → Einstellungen holen → Konfiguration → Auftrag lesen → [Wächter 1]
                                                                     ↓
   [Wächter 2] ← Zuständigkeit prüfen ← Dokument laden ← Tags laden
        ↓
   pending setzen → Arbeit (sub-…) → Kommando + pending in EINEM Aufruf weg
```

**Wächter 1: keine Dokument-ID im Aufruf.** Ein Consumption-Auslöser ruft ohne
`doc_url` auf, weil das Dokument zu dem Zeitpunkt noch nicht existiert
(Paperless setzt den Platzhalter dann auf einen leeren String).

**Wächter 2: Kommando-Tag hängt nicht dran, oder es läuft schon etwas.**

Beide steigen **still** aus: HTTP 200, Ergebnis `{"status": "übersprungen",
"grund": "…"}`, kein Fehler, keine Mail. Der Grund steht im Ergebnis, damit
nachvollziehbar bleibt, *warum* nichts passiert ist. Ein zusätzlicher Auslöser
erzeugt damit Leerläufe statt Schaden.

### Der globale Tag `wird bearbeitet`

Er gehört keinem Workflow, sondern dem Dokument: solange er hängt, ruht dort
**jede** n8n-Verarbeitung. Er hat zwei Aufgaben.

*Schleifenschutz.* Der Sub schreibt Text und Titel zurück. Das ist selbst
wieder eine Dokumentänderung und ruft den Workflow erneut auf. Wächter 2 sieht
dann den pending-Tag und steigt aus.

*Sperre gegen Doppelausführung.* Ein Ergebnis-Tag allein genügt nicht: zwei
überlappende Läufe sähen beide „noch nicht erledigt". Bei den Versand-Workflows
wäre das ein doppelt verschickter Beleg.

Am Ende verschwinden Kommando- und pending-Tag in **einem** `bulk_edit`. Der
Zustand danach trägt keinen von beiden, der Auslöser greift also nicht erneut.

Der Paperless-Auslöser bekommt zusätzlich `filter_has_not_tags: ["wird
bearbeitet"]`. **Der Filter ist eine Optimierung**; er verhindert den
überflüssigen Aufruf. Die Garantie liegt in n8n. Wer den Filter entfernt,
bekommt einen Leerlauf, keine Schleife.

### Ergebnis-Tags: nicht überall

| Art | Beispiel | Ergebnis-Tag? |
| --- | --- | --- |
| Versand | `Steuer-gesendet`, `sevdesk-gesendet` | **ja**: Ein zweiter Versand muss für immer ausgeschlossen sein |
| Erkennung | Titel, OCR, Custom Fields | **nein**: Wiederholen ist erwünscht; wem der Titel nicht gefällt, der setzt den Tag erneut |

### Der Fehlerfall

`wird bearbeitet` bleibt absichtlich hängen. Würde der Workflow ihn beim
Abbruch entfernen, wäre das wieder eine Dokumentänderung, und weil der
Kommando-Tag noch dranhängt, entstünde eine Endlos-Wiederholung. Das
Dokument steht also sichtbar auf „wird bearbeitet", `fehler-melden` schickt
eine Mail, und `paperless-health-check` meldet, was länger als zwei Stunden so
steht. **Nicht automatisch aufräumen**, weil das eine unbegrenzte
Wiederholschleife auf einem kaputten Dokument wäre.

### Was das messbar gebracht hat

Ein Tag-Setzen an einem Testdokument, vorher und nachher:

| | vorher | nachher |
| --- | --- | --- |
| Paperless-WorkflowRuns | 2 | 1 |
| Mistral-OCR-Durchgänge | 2 | 1 |
| Aufruf ohne Dokument-ID | 6 Fehlermails | stiller 200er |

### `sub-`-Workflows

Alles mit dem Präfix `sub-` ist Bibliothek: kein eigener Trigger, nur ein
Execute-Workflow-Trigger, ausschließlich über seinen Aufrufer erreichbar. Dafür
gelten drei Regeln.

**Immer `;true` in `workflows.list`.** n8n 2.x holt beim Aufruf die
*veröffentlichte* Fassung; ein unveröffentlichter Sub ist ein stiller
Totalausfall seines Aufrufers. Als Regel für alle ist das billiger als eine
Einzelfallabwägung.

**Eingaben werden definiert, nicht durchgereicht.** Der Trigger nutzt
`inputSource: workflowInputs` mit benannten Feldern. Mit `passthrough` hängt der
Sub davon ab, was im Datenstrom des Aufrufers zufällig oben liegt.

**Konfiguration wird nach unten durchgereicht, nicht auf jeder Ebene neu
beschafft.** `sub-einstellungen` wird einmal pro Lauf aufgerufen; die Werte
gehen als Eingabe an tiefere Subs. Sonst stehen vier Einträge in der
Ausführungsliste statt zwei.

> **Nicht versucht:** `saveDataSuccessExecution: "none"`, um Bibliotheksaufrufe
> aus der Liste herauszuhalten. Das hinterlässt in n8n 2.32.7 Einträge im Status
> `running`, die nie aufgeräumt werden.

## Steuerversand: drei Kanäle, ein Vertrag

Für den Nutzer gibt es genau eine Handlung: Tag `Steuer-senden` dranhängen. Er
soll nicht wissen müssen, ob seine Kanzlei DATEV Unternehmen online benutzt.
Der Betreiber weiß es und hängt den passenden Unterbau ein.

```text
Auswahl - wer und wann                    Versand - wie und wohin

steuer-beleg-sofort                       sub-duo-versand
  Webhook, Kommando-Tag Steuer-senden       n Mails mit je einem Anhang
  ein Beleg                          ──┐
                                       │   sub-stb-versand
                                       ├──>  EINE Mail, Zip + CSV-Belegliste
steuer-beleg-monatslauf                ──┘
  Zeitplan, Auswahl buchungsrelevant       sub-sevdesk-versand
  n Belege                                   n Mails an die Autobox

                                          EINER von dreien, laut pw_config
```

### Warum drei Versand-Subs und nicht einer mit Schalter

Weil sie sich nicht nur im Empfänger unterscheiden, sondern in der Form:
DUO und sevDesk schicken *n* Mails mit je einem Anhang, StB schickt *eine* Mail
mit *n* Anhängen im Zip. Ein gemeinsamer Workflow müsste diese Formen mit
if/else in einem Datenfluss vereinen, und jede spätere Änderung an einem Kanal
liefe Gefahr, die anderen zu treffen. Das sind getrennte Welten, auch wenn zwei
davon sich ähneln: sevDesk hat einen eigenen Absender, weil die Autobox Mail von
nicht hinterlegten Adressen stillschweigend verwirft.
Monatslauf und Sofortversand eines Kanals rufen denselben Sub auf, damit sie
nicht auseinanderlaufen. Ein Beispiel für solche Abweichungen: Ein Betreff aus
`$('Loop über Belege').first().json.title` statt `.item` gibt bei zehn Belegen
allen zehn Mails den Titel des ersten Dokuments.
Stelle richtig. Genau dafür gibt es den Sub.

### Der Kanal steht in `pw_config`, nicht im Workflow

Ein Kanalwechsel ist **eine Zeile in der Data Table**: Schlüssel
`steuer_kanal`, Werte `duo`, `duo_paperwerk`, `stb` oder `sevdesk`. Umstellbar in der
n8n-Oberfläche unter „Data Tables", ohne Deploy und ohne Neustart. Ein
unbekannter Wert bricht mit einer Meldung ab, die die erlaubten aufzählt.

| `steuer_kanal` | Empfänger | Absender | Versand-Sub |
| --- | --- | --- | --- |
| `duo` | `mail_duo` | `mail_absender` | `sub-duo-versand` |
| `duo_paperwerk` | `mail_duo` | `mail_absender` | `sub-duo-versand-paperwerk` |
| `stb` | `mail_stb` | `mail_absender` | `sub-stb-versand` |
| `sevdesk` | `mail_sevdesk` | `mail_sevdesk_absender` | `sub-sevdesk-versand` |

> **Der Kanal steht nicht im Workflow.** Die Dateien unter `n8n/` teilen sich
> ALLE Instanzen, und eine fährt DUO, eine andere sevDesk. Fest verdrahtet
> bekäme eine von beiden beim Einspielen den falschen Kanal untergeschoben. **Was sich je Instanz
> unterscheidet, gehört in `pw_config`, auch dann, wenn es im Canvas
> unsichtbar wird.** Sichtbar bleibt es im Ergebnis des Konfigurations-Knotens,
> der `kanal` und `versand_sub` ausgibt.

Beide Selektoren lesen denselben Schlüssel und können daher nicht mehr
auseinanderlaufen.

**`duo_paperwerk`** ist DUO für Installationen **mit**
paper-werk: Ist ein Beleg eine XRechnung aus paper-werk, hängt
`sub-duo-versand-paperwerk` das abgelegte XML als zweiten Anhang an die Mail.
Paperless mit n8n ohne paper-werk ist eine ebenso legitime Installation und
fährt weiter `duo`; `sub-duo-versand` weiß von paper-werk nichts. Zwei
Dateien statt einer Weiche im Ablauf, weil dies der erste Kanal ist, der
einen Unterschied macht. Voraussetzung: `paperwerk_url` in `pw_config` und
die Credential „Header Auth paper-werk“; fehlt eins, bricht der Lauf ab.

Alle Subs nehmen dieselben sieben Eingaben:

| Eingabe | Typ | Bedeutung |
| --- | --- | --- |
| `doc_ids` | Liste | Paperless-IDs der zu sendenden Belege |
| `paperless_url` | Text | |
| `empfaenger` | Text | je nach Kanal aus `pw_config`, siehe Tabelle oben |
| `absender` | Text | bei DUO die dort bestätigte, bei sevDesk die in der Autobox hinterlegte Adresse |
| `dateiname_quelle` | Text | `titel` oder `original` |
| `zeitraum` | Text | Label für Betreff und Dateinamen |
| `tag_gesendet_id` | Zahl | Paperless-ID von `Steuer-gesendet` |

**`doc_ids` ist eine Liste, auch beim Sofortversand mit genau einem Beleg.**
Ein Sub, der einen einzelnen Beleg nimmt, könnte kein Zip bauen; der StB-Kanal
wäre damit gar nicht ausdrückbar. Die Liste ist die kleinste Form, die alle
Kanäle bedient. `array` ist als Eingabetyp im `executeWorkflowTrigger` gültig
(siehe `TYPE_OPTIONS` in `workflowInputsResourceMapping/constants.js`, geprüft
mit n8n 2.32.7).

### Wer setzt welchen Tag

| Tag | gesetzt von | entfernt von |
| --- | --- | --- |
| `Steuer-senden` | Mensch | dem Auswahl-Workflow, **nach** dem Versand |
| `wird bearbeitet` | Auswahl-Workflow (nur Sofortfall) | demselben, zusammen mit dem Kommando in *einem* Aufruf |
| `Steuer-gesendet` | Versand-Sub | niemandem, er ist der Doppelversand-Schutz |

Der Monatslauf setzt **kein** `wird bearbeitet`: er hängt an einem Zeitplan,
eine Schleife kann gar nicht entstehen. Er *schließt* aber Dokumente aus, die
so markiert sind. Dort arbeitet gerade ein anderer Lauf, und zwei Versender am
selben Beleg wären ein Doppelversand.

### Drei Ausgänge im Sofortfall

`senden`, `quittieren` (schon gesendet: Nichts geht raus, aber der Kommando-Tag
muss weg, sonst hängt er für immer) und `nichts` (stiller Ausstieg). Alle drei
sind durchgespielt, dazu die beiden Wächter-Fälle „Aufruf ohne Dokument-ID"
und „`wird bearbeitet` hängt dran". Ergebnis: **ein** Paperless-WorkflowRun und **drei** n8n-Ausführungen pro
echtem Versand (Auswahl + `sub-einstellungen` + Versand-Sub).

**`buchungsrelevant` wird im Sofortfall bewusst nicht verlangt.** Beim
Monatslauf ist es das Auswahlkriterium; im Sofortfall hat ein Mensch das
Dokument ausdrücklich markiert, und *das* ist die Entscheidung. Ein zusätzlich
nötiges zweites Tag wäre eine Falle: der Nutzer setzt `Steuer-senden`, es
passiert nichts, und niemand sagt ihm warum.

### Grenzen

Beide Subs brechen ab, wenn Paperless weniger Belege zurückliefert als
angefordert. 250 ist die Seitengröße, und ein zwischenzeitlich gelöschtes
Dokument käme sonst gar nicht zurück. Ein nicht gesendeter Beleg, den niemand
vermisst, ist der teurere Fehler. Der Monatsbericht sagt zusätzlich
ausdrücklich, wenn mehr als 250 anlagen; ein zweiter manueller Lauf holt den
Rest nach, weil er nur nimmt, was `Steuer-gesendet` noch nicht trägt.

## Konvention: Tags als Auslöser

Paperless kennt keinen Auslöser „*in dem Moment*, in dem Tag X drangehängt
wurde". Es gibt nur „Dokument aktualisiert **und** hat Tag X“, eine Bedingung,
die weiter gilt, solange das Tag dranhängt. Schreibt der ausgelöste
n8n-Workflow danach etwas ins Dokument zurück (Titel, Custom Field), ist das
selbst wieder eine Änderung: der Ablauf feuert erneut, endlos. **Ein Tag als
Auslöser muss nach der Verarbeitung verschwinden.** Die Frage ist nur, wer das
tut.

### Drei Tag-Klassen

| Klasse | Form | Beispiele | Lebensdauer |
| --- | --- | --- | --- |
| **Kommando** | Verb, imperativ | `titel-verbessern`, `vertrag-erkennen`, `Steuer-senden` | wird verbraucht |
| **Ergebnis** | Partizip | `Steuer-gesendet`, `sevdesk-gesendet`, `fehler-titel` | bleibt |
| **Sache** | Substantiv | `Steuer`, `Privat`, `Wichtig` | bleibt, gehört dem Menschen |

Daraus die Regel: **Ein Typ-3-Auslöser („Dokument aktualisiert") darf
ausschließlich auf Kommando-Tags filtern.** Filtert er auf ein Sach-Tag oder
einen Dokumenttyp, ist die Schleife eingebaut und nicht mehr zu schließen: Das
Merkmal lässt sich ja nicht entfernen, es beschreibt das Dokument. Ein Dateiname ist derselbe Fall: `scan*` beschreibt das
Dokument und lässt sich nicht verbrauchen.

### Automatik: Paperless erteilt den Auftrag, nicht n8n

Was aber, wenn etwas *ohne* menschliches Zutun laufen soll, etwa „jeder Scan aus
dem Handschrift-Fach soll durch die Mistral-OCR"? Naheliegend wäre, dem
n8n-Workflow das Kriterium beizubringen. Falsch: dann steht es in Paperless
**und** in n8n und läuft irgendwann auseinander.

> **Ein Auftrag ist ein Tag, auch ein automatischer.**

Es gibt zwei Wege, den Tag automatisch zu vergeben. Beide enden im selben
Zustand, und n8n kennt die Automatik in beiden Fällen gar nicht.

**Weg 1: der Unterordner.** `PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS=true` (zusammen
mit `PAPERLESS_CONSUMER_RECURSIVE=true`) vergibt Tags nach dem Unterordner im
consume-Verzeichnis. Am Scanner wählt man das Ziel, Paperless macht daraus den
Tag. So läuft `handschrift-scannen`: **Ordnername = Tagname**, und wer den
einen umbenennt, muss den anderen mitbenennen, sonst legt Paperless still
einen zweiten Tag an und der Ablauf feuert nicht mehr.

> **Einrichtungsschritt, den `apply.sh` NICHT erledigt.** Es arbeitet rein über
> die API und kennt den consume-Pfad gar nicht (ein Docker-Volume oder ein
> Ordner auf dem Host). Der Unterordner muss von Hand angelegt werden, exakt
> so heißen wie der Tag und Paperless gehören, sonst kann der Consumer die
> Datei nach dem Einzug nicht löschen:
>
> ```bash
> docker compose exec -u root paperless \
>   sh -c 'mkdir -p /usr/src/paperless/consume/handschrift-scannen &&
>          chown paperless:paperless /usr/src/paperless/consume/handschrift-scannen'
> ```
>
> Danach am Scanner ein zweites Ziel auf diesen Ordner einrichten. Der Tag
> selbst muss nicht vorab existieren, Paperless legt ihn beim ersten Scan an;
> er steht trotzdem in `tags.json`, damit Farbe und Kommentar stimmen und die
> Abläufe ihn beim Einspielen auflösen können.

**Weg 2: eine Zuweisungs-Aktion.** Für alles, was sich nicht am Ablageort
festmachen lässt (Dateiname, Korrespondent, Dokumenttyp). Der Auslöser bekommt
die Zuweisung, und erst danach den Webhook:

```text
Auslöser  Dokument hinzugefügt (Typ 2), Dateiname scan*
Aktion 1  Tag "…-erledigen" zuweisen        <- erteilt den Auftrag
Aktion 2  Webhook an n8n
```

Vier Dinge, die dabei zählen (am Quelltext von Paperless geprüft):

- **Der Unterordner-Tag hängt schon am fertigen Dokument.** `consumer.py`
  wendet die Overrides in `_store` an und speichert; erst danach feuert
  `document_consumption_finished`. Ein Typ-2-Auslöser mit `filter_has_tags`
  sieht ihn also. Umgekehrt heißt das: **ein Ablauf, der nur Typ 3 hat,
  verpasst diese Dokumente vollständig**, weil es keine Änderung gibt. Wer
  beide Wege offenhalten will (Unterordner *und* Tag von Hand), braucht zwei
  Auslöser auf demselben Tag.
- **Bei Weg 2 ist die Reihenfolge nicht kosmetisch.** `run_workflows` arbeitet
  `actions.order_by("order", "pk")` ab, und der Serializer vergibt `order` aus
  der **Listenposition** (`action["order"] = index`). Das Feld lässt sich also
  nicht von Hand setzen, es zählt allein, wie die Aktionen in `workflows.json`
  stehen. `add_nested_tags` schreibt sofort in die Datenbank, der Webhook wird
  nur als Hintergrund-Task eingereiht. Steht die Zuweisung dahinter, kann n8n
  ein Dokument abrufen, das den Auftrag noch nicht trägt.
- **Typ 2 ist Pflicht, Typ 3 wäre eine Schleife.** „Dokument hinzugefügt" feuert
  genau einmal je Dokument. Bei Typ 3 mit Dateimuster würde jedes Zurückschreiben
  erneut auslösen, und die Zuweisung setzte den gerade verbrauchten Tag wieder.
- **Ein Typ-2-Auslöser, der ein Tag setzt, weckt keinen Typ-3-Auslöser.** Beim
  Einzug sendet Paperless nur `document_consumption_finished`; das Signal
  `document_updated` wird ausschließlich an fünf Stellen explizit gesendet
  (`consumer.py`, `tasks.py`, `views.py`) und **nicht** von Workflow-Aktionen;
  die speichern mit `document.save(update_fields=…)`. Deshalb braucht der
  Auslöser den Webhook selbst; darauf zu hoffen, dass der Tag den
  Tag-Auslöser weckt, funktioniert nicht.

Der Nebeneffekt ist erwünscht: schlägt der Lauf fehl, bleibt der Kommando-Tag
am Dokument hängen. Die automatisch angestoßenen Fälle stehen damit genauso
in der Liste der offenen Aufträge wie die von Hand gesetzten. Nach einem
behobenen Fehler genügt es, das Dokument erneut anzufassen.

**Zwei Automatiken dürfen sich nicht überschneiden.** Ein Scanner benennt jede
Datei `scan_nnn.pdf`, egal, in welches Fach sie geht. „Titel erzeugen“ hängt
am Dateimuster, „Handschrift-OCR" am Unterordner-Tag, und ohne weiteres Zutun
greifen bei einem Handschrift-Scan **beide** und erzeugen gleichzeitig einen
Titel. Deshalb schließt der billigere Ablauf den teureren per
`filter_has_not_tags` aus. Faustregel: Wer eine zweite Automatik auf denselben
Dokumentenstrom setzt, prüft zuerst, ob die erste ihn schon anfasst.

> **`sources` steht in vielen Auslösern, wirkt aber nur bei Typ 1.** Paperless
> wertet es in `consumable_document_matches_workflow` aus; bei Typ 2 und 3 ist
> das Objekt längst ein echtes `Document` und hat keine Quelle mehr. `[]` und
> `[1, 2, 3]` verhalten sich dort identisch.

### Wer räumt auf

> **Wer den Auslöser definiert, besitzt dessen Lebenszyklus.**

Der Paperless-Arbeitsablauf ist der Auftraggeber: Er legt fest, dass Tag X
„tu Y" bedeutet. Also quittiert *er* den Auftrag, per Aktion Typ 2
(`remove_tags`). Der n8n-Workflow bekommt eine `doc_url` und liefert ein
Ergebnis; er weiß gar nicht, dass es ein Tag gibt. So bleibt er eine reine
Funktion, die tut, was ihr Name sagt.

Praktisch wichtig dabei: Paperless reiht den Webhook als Hintergrund-Task ein
(`send_webhook.apply_async`), entfernt das Tag aber sofort in der Datenbank.
Wenn n8n den Aufruf bekommt und das Dokument nachlädt, ist das Kommando-Tag
also längst weg, **egal in welcher Reihenfolge die Aktionen im Ablauf stehen**.
Ein Worker darf sich nie darauf verlassen, dass sein Auslöser-Tag noch dran ist.

### Ausnahme: Quittung erst nach Erfolg

Manchmal darf nicht sofort quittiert werden. `handschrift-ocr-titel-mistral`
ersetzt den OCR-Text; scheitert Mistral, steht noch der Tesseract-Text im
Dokument und der Auftrag muss erhalten bleiben. Dann gehört das Ack ans
Ergebnis, und zwar in einen zweiten Workflow. Das
Paar heißt `<name>` (Protokoll, hält Webhook-Pfad und ID) und `<name>-kern`
(reine Funktion):

```text
handschrift-ocr-titel-mistral           Auftragsannahme
  Webhook -> Auftrag lesen -> Arbeit ausführen -> Quittieren: Tag entfernen
                                    |
                                    v
handschrift-ocr-titel-mistral-kern      reine Funktion
  doc_url -> neuer OCR-Text + neuer Titel        kennt keine Tags
```

Für einen Workflow namens „Auftragsannahme" ist Quittieren keine Magie, sondern
die Aufgabe. Der Einwand trifft die Vermischung, nicht die Sache. Umgesetzt ist
das bei `handschrift-ocr-titel-mistral` und `steuer-beleg-sofort`.

Beim Steuerversand zeigt sich die Aufteilung besonders klar: `Steuer-senden` ist
das Kommando und wird außen entfernt, `Steuer-gesendet` ist ein **Ergebnis** und
wird im Versand-Sub gesetzt, weil nur der weiß, ob die Mail rausging. Und quittiert
wird auch, wenn nichts zu senden war: der Auftrag ist bearbeitet, das Tag muss
weg, sonst hängt es für immer am Dokument.

> **Namenshinweis.** Das Suffix `-kern` ist aufgegeben. Es sagte, wo ein
> Workflow im Aufrufbaum steht, aber nicht, wozu er gut ist, und es gab keinen
> Namen für Bibliotheken, die *mehrere* Aufrufer haben. Heute gilt einheitlich
> `sub-` (siehe „`sub-`-Workflows").

Vier Dinge, die dabei zählen:

- **Der Kern muss veröffentlicht sein.** n8n 2.x holt beim Aufruf über
  `getPublishedWorkflowData` die veröffentlichte Fassung und bricht sonst mit
  `Workflow is not active and cannot be executed` ab; unter 1.x war das nicht
  nötig. In `workflows.list` steht der Kern deshalb auf `;true`, sobald sein
  Aufrufer aktiv ist. „Aktiv" heißt hier nicht „von außen erreichbar": der Kern
  hat keinen eigenen Trigger, nur einen Execute-Workflow-Trigger.
- **Der Kern bekommt keinen eigenen `errorWorkflow`.** Sonst meldet jede
  Störung zweimal. n8n reicht die Fehlermeldung des Sub-Workflows an den
  Aufrufer durch, dessen Mail nennt sie also ohnehin.
- **Der Kern liest sein Item direkt, nicht aus `.body`.** Ein Webhook liefert
  `{ body: {...} }`, ein Execute-Workflow-Trigger das Item selbst. `wh.body ?? wh`
  deckt beides ab und hält den Kern für Handtests im Editor brauchbar.
- **Ein Fehlerzweig ist nicht nötig.** Bricht der Kern ab, bricht der Aufrufer
  mit ab, das Kommando-Tag bleibt am Dokument hängen und `fehler-melden`
  schickt eine Mail. Damit sind **die noch getaggten Dokumente die Liste der
  offenen Fälle**. Ein eigenes `fehler-*`-Tag braucht es nur dort, wo das
  Kommando-Tag schon vorher entfernt wurde.

## Fehlerbehandlung in zwei Ebenen

Die beiden Ebenen wissen Verschiedenes:

| | weiß | Aufgabe |
| --- | --- | --- |
| `fehler-melden` (global) | Workflow, Node, Stack, Execution-URL | einen **Menschen** informieren |
| Auftrags-Wrapper | die `doc_url` | das **Dokument** markieren |

Der n8n-Error-Trigger bekommt die Item-Daten des gescheiterten Laufs **nicht**.
Er kann melden, dass
*Felder erkennen (Mistral)* an Node *Mistral extract* gescheitert ist; welches
Dokument betroffen war, weiß er nicht. Deshalb geht die Mail an eine feste
Betreiber-Adresse und nicht an den Dokumentbesitzer; technisch ginge es gar
nicht anders, und inhaltlich wäre ein Stack Trace beim Endnutzer ohnehin falsch.

Ein Protokoll-Workflow darf den Fehler seines Kerns deshalb **nicht abfangen**.
Wird er abgefangen und behandelt, gilt die Execution als erfolgreich und
`fehler-melden` feuert nicht. Man hätte das Dokument-Merkmal gegen die Mail
getauscht statt beides zu haben. Einfach durchbrechen lassen: dann bleibt das
Kommando-Tag hängen (Dokument-Merkmal) **und** die Mail geht raus. Braucht man
darüber hinaus ein eigenes `fehler-*`-Tag, lautet das Muster
**fangen → markieren → bewusst scheitern** (`Stop and Error`).

Verdrahtet wird per `"settings": { "errorWorkflow": "pwFehlerMelden01" }` im
Workflow-JSON, geht also durch den normalen Import mit. Zwei Fallen, beide
praktisch geprüft:

- **`fehler-melden` muss selbst aktiv sein.** Sonst steht im n8n-Log nur
  `Workflow ... is not active and cannot be executed`. Alles sieht verdrahtet
  aus, es passiert nichts.
- **Nur Produktionsläufe lösen aus.** Ein manuelles „Test workflow" im Editor
  ruft den Error Workflow nicht auf.

**Mailflut:** Ein Massenimport bei ausgefallener Cloud-API erzeugt sonst eine
Mail pro Dokument. `fehler-melden` drosselt deshalb über eine Signatur aus
Workflow, Node und Fehlermeldung mit **maskierten Ziffern**. Ohne die
Maskierung wäre jeder Fehler wegen der enthaltenen Dokument-IDs eine eigene
Signatur. Gemeldet wird beim 1., 10., 100. und 1000. gleichartigen Fehler pro
Stunde, dazu eine harte Obergrenze über alle Signaturen. 300 gleichartige
Fehler ergeben so 3 Mails statt 300, die erste sofort. Der Zustand liegt in den
Static Data des Workflows (`$getWorkflowStaticData`), überlebt Läufe und
braucht keinen externen Speicher.

**Der Handler ist der einzige Punkt, der sich nicht selbst überwacht:**
Scheitert er, verschluckt n8n das kommentarlos, um Fehlerschleifen zu
vermeiden, ohne Logeintrag. Deshalb nach dem Einrichten einmal
`fehler-melden-test` aktivieren, `curl .../webhook/fehler-melden-test`,
Postfach prüfen, wieder deaktivieren.

## Eingebaute Stolperfallen-Vermeidung

- n8n-CLI-Import setzt `active` auf false zurück → Skript aktiviert explizit
  per `update:workflow` und startet danach den Container neu (die laufende
  Instanz sieht DB-Änderungen erst nach Restart), dann `healthz`-Poll.
- **Workflows loswerden:** Die n8n-CLI kann Workflows weder löschen noch
  archivieren; sie kennt nur `export/import/list/publish/unpublish/update`.
  In der Oberfläche gilt außerdem „erst archivieren, dann löschen". Archivieren
  ist eine Spalte in der Datenbank und lässt sich direkt setzen:

  ```bash
  docker exec <n8n-container> node -e "
  const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/.pnpm/sqlite3@5.1.7/node_modules/sqlite3');
  new sqlite3.Database('/home/node/.n8n/database.sqlite').run(
    \"UPDATE workflow_entity SET isArchived=1, active=0, activeVersionId=NULL WHERE id IN ('...')\");
  "
  ```

  `active` und `activeVersionId` gehören mit zurückgesetzt, weil archiviert und
  gleichzeitig aktiv ein unschöner Zwischenzustand wäre. Danach n8n neu
  starten; die Workflows liegen dann in der Oberfläche unter „Archived" und
  lassen sich dort löschen. **Achtung:** `n8n list:workflow` zeigt archivierte
  Workflows weiterhin an. Für `n8n/apply.sh` gilt ein archivierter Workflow
  deshalb als „existiert bereits“ und wird übersprungen. Wer etwas archiviert
  und dann neu einspielen will, braucht `--force`.
- Paperless-Objekte werden per Name auf Existenz geprüft → mehrfaches
  Ausführen legt nichts doppelt an (Skip, kein Überschreiben).
- Kopia: erst `repository connect` versuchen, dann `create` → funktioniert
  für Erstinstallation **und** Wiederanbindung an ein bestehendes Repo
  (Disaster-Recovery-Pfad, siehe `docs/kopia-backblaze.md`).
- Cloud-Zugangsdaten stehen nach der Einrichtung **nur** in der Kopia-Config im
  Container-Volume → Skript erinnert daran, sie extern zu sichern.
- Cloud-Ziel ist `KOPIA_REPO_TYPE="s3"`, auch für Backblaze B2: Kopias eigener
  `b2`-Provider ist deprecated und meldet das bei jedem Aufruf. `b2` wird noch
  akzeptiert (Altinstallationen), warnt aber. **Bestehende b2-Installation
  umstellen:** Ablauf, Stolpersteine und Verifikation in
  `docs/kopia-backblaze.md`, Abschnitt „Neuverbindung: Endpunkt- oder
  Key-Wechsel“. Es ist ein reiner Verbindungswechsel ohne Datenbewegung.
- Bei Backblaze erinnert das Skript nach dem Verbinden an die beiden Dinge, die
  es selbst nicht setzen kann, weil sie im Backblaze-Konto liegen: die
  Lifecycle-Regel des Buckets (sonst bleiben gelöschte Blobs für immer liegen
  und werden berechnet) und einen auf das Bucket beschränkten Application Key.

## Ausbaustufen (bewusst noch nicht im Gerüst)

- **Update-Modus für Paperless-Objekte**: bestehende Tags/Workflows per PATCH
  angleichen statt nur zu überspringen (Erst-Scope war „anlegen").
- **Noch nicht eingespielt**: Mail-Regeln (`/api/mail_accounts/`,
  `/api/mail_rules/`) sowie Nutzer und Gruppen.
- Paperless-Arbeitsabläufe mit Webhook-Aktion (Typ 4) werden unterstützt,
  inkl. Namensauflösung in `triggers[].filter_has_tags`/`filter_has_document_type`
  (analog zu `actions[].assign_*`; Paperless lehnt Namen in `triggers[]` mit
  "Incorrect type" ab). Die n8n-Ziel-URL (`http://n8n:5678/webhook/...`)
  steht als fester String in `workflows.json` und wird nicht aus der
  Zielumgebung abgeleitet. Die Auflösung deckt alle Zuweisungs- und
  Filterfelder ab (auch `filter_has_all_tags`,
  `remove_tags`, `assign_storage_path`, `assign_custom_fields[_values]`,
  `assign_owner`, `assign_view_groups`/`assign_change_groups`), nötig für
  gewachsene Installationen.
- **n8n-Workflows werden an der ID erkannt, nicht am Namen.** Bei einer
  gewachsenen Installation, in der Workflows erst in der Oberfläche entstanden
  und später ins Repo kamen, laufen Repo-ID und Instanz-ID auseinander. Ein
  Import legt dann einen zweiten, gleichnamigen Workflow an statt zu
  aktualisieren. Vor dem ersten Lauf auf so einer Instanz abgleichen.
- Superuser/Token-Erzeugung automatisieren (`manage.py drf_create_token`),
  statt den Token manuell in `setup.conf` einzutragen.
- Kopia-Benachrichtigungen (Mail) per Skript konfigurieren.
