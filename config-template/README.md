# Konfiguration einer Installation

Dieser Ordner ist die Vorlage für `config/` (eine Installation je Rechner)
oder ein Config-Repo unter `config-repos/` (siehe
`config-repos/README.md` in paper-werk).

| Datei | Inhalt | Im Git |
| --- | --- | --- |
| `instanz.conf` | Projektname, HTTPS, Profile, eigene Compose-Zusätze | ja |
| `.env`, `.env.*` | Pfade, Kennwörter, Namen dieser Installation; aus den `*.example` | nein |
| `einstellungen/` | Werte für die Setup-Skripte; `setup.conf` und `n8n/credentials.json` aus den `*.example` | ja, außer den beiden |
| `einstellungen/paperless/starterpaket/` | entsteht mit `setup/paperless/starterpaket-zusammenstellen.sh` | ja |
| `compose.override.yml` | optional: Änderungen vor Ort, wird immer zuletzt dazugenommen | ja |
| `zertifikate/` | nur bei `PAPER_WERK_TLS_MODE=datei` | nein |

Anlegen, aus der Wurzel von paper-werk:

```bash
cp -r config-template config
cd config
for v in .env*.example; do cp -n "$v" "${v%.example}"; done
cp einstellungen/setup.conf.example einstellungen/setup.conf
cd ..
./setup/paperless/starterpaket-zusammenstellen.sh config [variante]
```

Danach `.env*` und `einstellungen/setup.conf` ausfüllen und starten:
`./paper-werk up`. Die `*.example` dürfen liegen bleiben;
`setup/env-abgleich.sh` vergleicht ohnehin mit `config-template/`.
