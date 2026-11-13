# Zugang und Authentifizierung

Anmeldung an Paperless-ngx und paper-werk-app bei Installationen, die über
einen Namen im Netz oder im Internet erreichbar sind. Paperless-ngx bietet
TOTP über allauth an, kann es aber serverseitig nicht erzwingen;
paper-werk-app hat eine eigene Nutzerverwaltung. Der zweite Faktor muss
deshalb von einem Identitätsanbieter vor beiden Anwendungen kommen.

## Anmeldung über Microsoft Entra ID

Für Betriebe mit Microsoft 365. Entra ID ist dort das vorhandene
Verzeichnis, und Mehrfaktor-Anmeldung lässt sich im Tenant über Security
Defaults oder Conditional Access erzwingen.

- **Paperless** meldet über allauth direkt bei Entra an (OpenID Connect,
  Bordmittel, Einstellungen nur in `.env.paperless`).
- **paper-werk-app** ebenso, über den generischen OIDC-Weg von
  django-allauth. Ein anderer OIDC-Anbieter braucht nur eine andere
  Discovery-Adresse und Client-Kennung in der `.env`.
- **Rolle gleich Gruppe.** Die App-Rollen im Entra-Portal heißen wie die
  Gruppen in beiden Anwendungen: `paper-werk-buero`,
  `paper-werk-projektleitung`, `paper-werk-superuser`. Jede Person bekommt
  genau eine Rolle.
- **Zwei Prüfungen.** Entra weist ab, wer der Anwendung nicht zugewiesen ist
  („Zuweisung erforderlich: Ja“). Danach weist paper-werk-app jedes Konto
  ohne paper-werk-Rolle ab, bevor es angelegt wird.
- **n8n und Kopia** sind nicht angebunden. Sie dienen der Betreuung und sind
  nur im Netz des Betriebs erreichbar.
- **Mehrfaktor-Anmeldung** wird im Tenant des Betriebs eingerichtet;
  paper-werk-app und Paperless prüfen sie nicht selbst.
- **Sicherung.** Die Zuordnung von Konto und Microsoft-Identität liegt in den
  Datenbanken von App und Paperless und ist damit im Kopia-Snapshot.

Einrichtung: `Kundeninstallation.md`, Abschnitt 7, und `setup/sso/`.

### Voraussetzungen

- **HTTPS.** Microsoft nimmt Rückleitadressen mit `http://` nur für
  `localhost` an. Eine Installation braucht deshalb einen Namen
  (`paper-werk.kunde.de`) und ein Zertifikat, entweder vom Administrator des
  Betriebs, etwa aus seiner Windows-Domäne, oder vom Stack selbst erzeugt
  (`HTTPS=ja`, siehe `docs/lokaler-name.md`).
- **Lizenz.** Im Entra-Tarif Free lassen sich App-Rollen nur einzelnen
  Personen zuweisen. Die Zuweisung an Gruppen verlangt Entra ID P1, das in
  Microsoft 365 Business Premium enthalten ist und in Business Standard
  nicht.

### Notfallzugang

Ist Microsoft nicht erreichbar, meldet sich der lokale Superuser über das
Passwortformular an. Es bleibt auch mit eingerichtetem Anbieter stehen. Der
Knopf „Anmelden mit Microsoft“ zeigt in diesem Fall eine Hinweisseite mit dem
Weg zurück zum Formular. In Paperless bleibt das Anmeldeformular stehen,
solange `PAPERLESS_DISABLE_REGULAR_LOGIN` nicht gesetzt ist; `/admin/` von
Paperless ist in jedem Fall erreichbar. Geprüft wurde das mit einer
Discovery-Adresse auf einen nicht existierenden Host.

## Schutz der Anmeldung in paper-werk-app

Die App sperrt die Anmeldung mit Passwort und drosselt die Schnittstelle.
Die Werte stehen in `.env.app`; die Vorgaben passen für den Betrieb.

| Variable | Vorgabe | Wirkung |
|---|---|---|
| `DJANGO_ANMELDUNG_VERSUCHE` | 5 | Fehlversuche je Benutzername und IP-Adresse bis zur Sperre |
| `DJANGO_ANMELDUNG_SPERRMINUTEN` | 15 | Dauer der Sperre |
| `DJANGO_API_RATE` | 600/min | Anfragen je Konto an die Schnittstelle |
| `DJANGO_API_FEHLVERSUCHE` | 10/min | ungültige API-Schlüssel je IP-Adresse bis zur Sperre |
| `DJANGO_HINTER_PROXY` | False | `X-Forwarded-Proto` und `X-Forwarded-For` auswerten |

- **`DJANGO_HINTER_PROXY`** setzt `compose.https.yml` auf `True`. Ohne den
  Wert sieht die App hinter Caddy jede Anfrage als HTTP von der Adresse des
  Proxys: Speichern scheitert an der CSRF-Prüfung, und die Anmeldesperre
  zählt alle Besucher zusammen. Ohne Proxy darf der Wert nicht gesetzt
  sein, weil der Client die beiden Header sonst selbst setzen kann.
- **Sperre aufheben.** Ein Administrator löscht den Eintrag unter
  Verwaltung > Anmeldesperren. Hat sich der einzige Administrator
  ausgesperrt:
  `./paper-werk compose exec paper-werk-app uv run --no-dev python manage.py axes_reset_username <name>`.
- **Externe Quellen.** Die Content-Security-Policy erlaubt Skripte,
  Stylesheets, Schriften und Bilder nur vom eigenen Server. Eine Anpassung,
  die etwas von außen lädt, muss die Quelle in `SECURE_CSP` ergänzen.

## Betrieb mit TOTP

- **Uhrzeit.** Weicht die Serveruhr ab, gilt kein Code mehr. NTP prüfen.
- **Wiederherstellungscodes** bei der Einrichtung ausgeben, damit ein
  zurückgesetzter zweiter Faktor nicht über Fernwartung erfolgen muss.
- **Grenze.** TOTP schützt nicht gegen Echtzeit-Phishing: Ein auf einer
  gefälschten Seite eingegebener Code gilt beim Angreifer 30 Sekunden.
  WebAuthn (Passkeys) prüft die Domain kryptografisch mit und schützt davor.

## Installationen ohne Verzeichnis

Für Betriebe ohne Microsoft 365 ist Authentik im Stack vorgesehen, aber
nicht umgesetzt: Forward-Auth vor paper-werk-app, OIDC für Paperless, ein
Enrollment Flow, der die TOTP-Einrichtung bei der ersten Anmeldung
erzwingt, ein Notfallzugang über einen getrennten Pfad und die
Authentik-Datenbank im Kopia-Snapshot. Zusätzlicher Bedarf: vier Container
(Server, Worker, PostgreSQL, Redis), etwa 1,5 bis 2 GB RAM.

## Verworfene Alternativen

- **Cloudflare Access.** Ein Identity-Aware Proxy vor der Installation, mit
  ausgehender Verbindung über `cloudflared`. Der Proxy terminiert TLS, die
  Dokumente liegen dort also im Klartext. Eine garantierte Terminierung in der
  EU gibt es nur mit der Data Localization Suite (Enterprise). Dazu kommen ein
  Limit von 100 MB je Anfrage auf Free und Pro, das große Sammelscans trifft,
  und Service Tokens für alles außer Browsern (n8n-Webhooks, API-Abrufe).
- **NetBird** (WireGuard-Mesh). Der Verkehr läuft direkt zwischen den Peers,
  braucht aber einen Client auf jedem Gerät.
- **Myra Security, Link11.** Terminieren TLS ebenfalls, ohne
  Selbstbedienungstarif.
- **Pomerium.** Ein Zugangsproxy ohne eigenes Nutzerverzeichnis, braucht also
  zusätzlich einen Identitätsanbieter.
- **Nur VPN** (WireGuard). Kein öffentlicher Zugang; Patchstand und
  Client-Einrichtung liegen vollständig beim Betreiber.
