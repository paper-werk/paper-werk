#!/usr/bin/env python3
"""Liest alle Dokumenttypen aus Paperless und gibt sie im Format von
document_types.json aus (Gegenstück zu setup/paperless/apply.sh).

Rein lesend: ändert weder die Instanz noch eine Datei, die Ausgabe geht nur ans
Terminal. Anleitung: document-types-exportieren.md

Aufruf:   python helpers/document_types_exportieren.py <projekt>
Beispiel: python helpers/document_types_exportieren.py dev

Nur Standardbibliothek, nichts zu installieren.
"""

import sys

from paperless_zugriff import gebe_json_aus, oeffne_projekt


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"Aufruf: {sys.argv[0]} <projekt>")
    api = oeffne_projekt(sys.argv[1])

    eintraege = []
    for typ in api("/api/document_types/?page_size=1000")["results"]:
        eintrag = {"name": typ["name"]}
        # "match" nur, wenn es einen Wert gibt: bei matching_algorithm 6
        # (automatisch) ist es leer und ohne Wirkung.
        if typ["match"]:
            eintrag["match"] = typ["match"]
        eintrag["matching_algorithm"] = typ["matching_algorithm"]
        eintrag["is_insensitive"] = typ["is_insensitive"]
        eintraege.append(eintrag)

    gebe_json_aus(eintraege)


if __name__ == "__main__":
    main()
