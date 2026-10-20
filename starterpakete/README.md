# starterpakete/

Paperless-Grundausstattung einer Installation: Tags, Dokumenttypen, Custom
Fields, Speicherpfade, Korrespondenten, Arbeitsabläufe, gespeicherte Ansichten.

```
starterpakete/
├── basis/      vollständiges Paket, gilt für jede Installation
└── elektro/    Variante: nur Ergänzungen zu basis/
```

Zusammengestellt wird mit

```bash
./setup/paperless/starterpaket-zusammenstellen.sh <installationsordner> [variante]
```

Ergebnis ist `<installationsordner>/einstellungen/paperless/starterpaket/`,
aus dem `setup.sh` (Modul `paperless`) einspielt. Danach gehört das Paket der
Installation; Änderungen an `starterpakete/` erreichen sie nur über ein
erneutes Zusammenstellen mit `FORCE=1`.

Eine Variante enthält nur, was `basis/` nicht hat. Ein Name in beiden ist ein
Abbruch, weil `apply.sh` jeden Namen nur einmal anlegt. Grund für die
Trennung: Mehrere Tags und Custom Fields hängen an n8n-Workflows und an
paper-werk-app; stünden sie in jeder Variante, liefen die Kopien auseinander.

Ein Eintrag ohne `name` ist ein reiner Kommentar und wird nicht eingespielt;
`_kommentar` in einem Eintrag mit Namen entfernt `apply.sh` vor dem POST. Eine neue Variante ist ein neuer Ordner mit den Dateien, die sie
ergänzt; fehlende Dateien bedeuten keine Ergänzung.
