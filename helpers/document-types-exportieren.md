# Dokumenttypen aus Paperless in die JSON übernehmen

Du hast in Paperless Dokumenttypen angelegt oder geändert und willst sie ins
Starterpaket (`document_types.json`) übernehmen. Das Skript
`document_types_exportieren.py` liest alle Typen aus und gibt sie im Format der
Datei aus.

Es ist rein lesend: Es ändert weder die Instanz noch eine Datei. Die Ausgabe
geht nur ans Terminal.

Die Quelle ist die API: `https://localhost:8005/api/document_types/` liefert
die Typen. `https://localhost:8005/` ist dabei die jeweilige Installation
(Adresse und Port hängen vom Projekt ab).

## Schritte

1. **Skript ausführen** (aus der Repo-Wurzel, Python 3 genügt):

   ```bash
   python helpers/document_types_exportieren.py dev
   ```

   `dev` ist der Name der Installation wie bei `./stack.sh`, `config` steht
   für `config/`. Das Skript nimmt
   Container und Token aus dessen `einstellungen/setup.conf`.
2. **Ausgabe in die `document_types.json`** des Projekts kopieren, z. B.
   `config-repos/paper-werk-config-dev/einstellungen/paperless/starterpaket/document_types.json`.
3. Committen. Der git-Diff zeigt, was sich gegenüber dem Starterpaket geändert
   hat.

## Was du wissen musst

- Ausgegeben werden `name`, `matching_algorithm` und `is_insensitive`, und
  `match` nur, wenn es einen Wert hat (bei „automatisch“, Algorithmus 6, ist es
  leer).
- **`_kommentar`** legt das Skript nicht an. Ersetzt du die Datei einfach,
  gehen die Kommentare der alten Datei verloren.
- Besitzer, Berechtigungen und die Anzahl der Dokumente kommen nicht mit.
- Die Reihenfolge ist die von Paperless, nicht die der alten Datei.

## Wenn es nicht läuft

- Läuft der Stack, und stimmt `PAPERLESS_CONTAINER` in der `setup.conf`?
- „setup.conf nicht gefunden“: Projektname falsch geschrieben.
- „Abruf gescheitert“: Stack läuft nicht, oder der Token in der `setup.conf`
  ist nach einem Neuaufsetzen ungültig.
