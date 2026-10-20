#!/usr/bin/env python3
"""Liest gespeicherte Ansichten aus Paperless und gibt sie im Format von
saved_views.json aus (Gegenstück zu setup/paperless/apply.sh).

Rein lesend: ändert weder die Instanz noch eine Datei, die Ausgabe geht nur ans
Terminal. Anleitung: views-exportieren.md

Aufruf:   python helpers/views_exportieren.py <projekt> [<ansicht-id>]
Beispiel: python helpers/views_exportieren.py dev 8   # ein Eintrag
          python helpers/views_exportieren.py dev     # alle, als Array

Nur Standardbibliothek, nichts zu installieren.
"""

import sys

from paperless_zugriff import gebe_json_aus, oeffne_projekt

# Welcher Regeltyp worauf zeigt: dieselbe Tabelle wie in
# setup/paperless/resolve-saved-view.jq, nur in die andere Richtung.
# Regeltyp 42 (Custom-Field-Abfrage) fehlt bewusst und bleibt roh, wie beim
# Einspielen.
REGELTYPEN = {
    "tags": (6, 17, 22),
    "correspondents": (3, 26, 27),
    "document_types": (4, 28, 29),
    "storage_paths": (25, 30, 31),
    "custom_fields": (38, 39, 40, 41),
}


def baue_eintrag(ansicht: dict, namen: dict, in_seitenleiste: bool) -> dict:
    """Macht aus einer API-Ansicht einen Eintrag für saved_views.json: IDs in
    Namen übersetzt, nur die Felder, die apply.sh wieder einspielt."""
    regeln = []
    for regel in ansicht["filter_rules"]:
        wert = regel["value"]
        for art, typen in REGELTYPEN.items():
            if regel["rule_type"] in typen and isinstance(wert, str):
                wert = namen[art].get(wert, wert)
        regeln.append({"rule_type": regel["rule_type"], "value": wert})

    eintrag = {
        "name": ansicht["name"],
        "show_in_sidebar": in_seitenleiste,
        "sort_field": ansicht["sort_field"],
        "sort_reverse": ansicht["sort_reverse"],
        "display_mode": ansicht["display_mode"],
        "filter_rules": regeln,
    }
    for feld in ("display_fields", "page_size"):
        if ansicht.get(feld):
            eintrag[feld] = ansicht[feld]
    return eintrag


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(f"Aufruf: {sys.argv[0]} <projekt> [<ansicht-id>]")
    projekt = sys.argv[1]
    ansicht_id = sys.argv[2] if len(sys.argv) == 3 else None

    api = oeffne_projekt(projekt)

    if ansicht_id:
        ansichten = [api(f"/api/saved_views/{ansicht_id}/")]
    else:
        ansichten = api("/api/saved_views/?page_size=1000")["results"]

    # ID→Name je Objektart, nur laden, was die Ansichten wirklich brauchen.
    benoetigt = {art for ansicht in ansichten for regel in ansicht["filter_rules"]
                 for art, typen in REGELTYPEN.items() if regel["rule_type"] in typen}
    namen = {art: {str(o["id"]): o["name"]
                   for o in api(f"/api/{art}/?page_size=1000")["results"]}
             for art in benoetigt}

    # "show_in_sidebar" gehört seit Paperless 3.x nicht mehr zur Ansicht, sondern
    # zu den UI-Einstellungen des Nutzers (Token-Inhaber). Hier wird es aus
    # deren sidebar_views_visible_ids gelesen, wie apply.sh sie beim Einspielen
    # schreibt.
    sichtbar = (api("/api/ui_settings/")["settings"]
                .get("saved_views", {}).get("sidebar_views_visible_ids") or [])

    eintraege = [baue_eintrag(a, namen, a["id"] in sichtbar) for a in ansichten]
    ausgabe = eintraege[0] if ansicht_id else eintraege

    gebe_json_aus(ausgabe)

if __name__ == "__main__":
    main()
