# Ein Name für den Server ohne DNS-Server

Gebraucht, sobald eine Installation HTTPS bekommt
(`HTTPS=ja` in `instanz.conf`, siehe `Kundeninstallation.md`, Abschnitt 7):
Ein Zertifikat gilt für einen **Namen**, nicht für `localhost` und nicht für
eine IP-Adresse.

Beim Kunden macht den DNS-Eintrag dessen IT. Auf einem Vorführrechner, in
einer Testumgebung oder in einem Büro ohne eigenen DNS-Server trägt man den
Namen selbst ein.

## Welcher Name

| Endung | Taugt? | Warum |
|---|---|---|
| `paper-werk.kunde.de` | **am besten**, wenn der Kunde eine Domain hat | Subdomain der echten Domain, eindeutig, die IT kann sie auch im eigenen DNS eintragen |
| `*.home.arpa` | **ja** | Seit 2018 für private Netze reserviert (RFC 8375). Wird nie im Internet vergeben. |
| `*.internal` | **ja** | Seit 2024 von der ICANN ebenfalls für private Netze vorgesehen. Liest sich freundlicher. |
| `*.local` | **nein** | Für mDNS/Bonjour reserviert (RFC 6762). Apple-Geräte lösen es nur darüber auf und **ignorieren die hosts-Datei**: „bei mir geht es, auf dem Mac nicht“. |
| `*.lan`, `*.home`, `*.intern`, `*.firma` | **nein** | Nicht reserviert. Kann jederzeit eine echte Endung werden, wie `.dev`, für die Browser seitdem HTTPS erzwingen. |

`.arpa` selbst ist die älteste Top-Level-Domain (vom ARPANET) und dient nur
der Infrastruktur, etwa dem Reverse-DNS (`…in-addr.arpa`). Deshalb hat man sie
noch nie in einer Adresszeile gesehen.

## Den Namen bekannt machen: die hosts-Datei

Jeder Rechner schaut **zuerst in seine hosts-Datei**, bevor er einen
DNS-Server fragt. Ein Eintrag dort ist ein DNS-Eintrag nur für diesen einen
Rechner.

| System | Datei |
|---|---|
| Windows | `C:\Windows\System32\drivers\etc\hosts` |
| macOS, Linux | `/etc/hosts` |

Eine Zeile je Name, IP-Adresse vorne:

```
127.0.0.1       ingenieurbuero.home.arpa     # auf dem Server selbst
192.168.1.50    ingenieurbuero.home.arpa     # auf jedem anderen Rechner im Netz
```

**Windows:** Editor per Rechtsklick *als Administrator ausführen*, dann die
Datei öffnen, im Dialog „Alle Dateien“ statt „Textdateien“ wählen, sonst ist
sie nicht zu sehen. **macOS/Linux:** `sudo nano /etc/hosts`.

Prüfen:

```bash
ping -n 1 ingenieurbuero.home.arpa     # Windows (Git Bash)
ping -c 1 ingenieurbuero.home.arpa     # macOS, Linux
```

Die Antwort muss von der eingetragenen Adresse kommen.

## Grenzen

- **Die hosts-Datei gilt nur für den Rechner, auf dem sie steht.** Bei zwei,
  drei Arbeitsplätzen geht das; darüber hinaus gehört der Name in den
  DNS-Server des Netzes, oft der Router (Fritz!Box: *Heimnetz → Netzwerk →
  Netzwerkeinstellungen → Lokaler DNS-Server* bzw. der Gerätename) oder der
  Domänencontroller.
- **Handys und Tablets** haben keine erreichbare hosts-Datei. Für sie geht es
  nur über den DNS-Server des Netzes.
- **Die IP des Servers muss fest sein** (im Router reservieren). Ändert sie
  sich, stimmen alle hosts-Einträge nicht mehr.
- **Browser merken sich Namen.** Nach einer Änderung hilft
  `ipconfig /flushdns` (Windows) und ein Neustart des Browsers.
