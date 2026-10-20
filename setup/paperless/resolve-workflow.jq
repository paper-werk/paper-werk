# Übersetzt einen Paperless-Arbeitsablauf aus workflows.json von NAMEN in die
# IDs der Zielinstanz. Wird von apply.sh per `jq -f` geladen (ausgelagert, damit
# die Auflösung ohne laufende Paperless-Instanz testbar bleibt).
#
# Erwartet die Name->ID-Maps als --argjson: tags, dts, sps, cfs, corrs, users, groups.
# Eingabe: ein einzelner Arbeitsablauf. Ausgabe: derselbe, POST-fertig.
#
# Rückwärtskompatibel: Aufgelöst wird nur, was als String dasteht. Zahlen gehen
# unverändert durch; ältere workflows.json mit rohen IDs funktionieren weiter.
#
# NICHT aufgelöst wird 'filter_custom_field_query': dort steckt die Feld-ID in
# einem serialisierten JSON-String, nicht in einem eigenen Feld. Solche Abläufe
# brauchen nach dem Einspielen eine Korrektur in der Paperless-Oberfläche.

# Einzelwert auflösen (nur Strings; Zahlen/null bleiben unangetastet).
def one($map; $kind):
  if type == "string" then ($map[.] // error("Unbekannt (" + $kind + "): " + .))
  else . end;

# Feld mit Skalarwert auflösen. has()-geprüft, weil "|=" ein fehlendes Feld
# sonst als null ANLEGEN würde; Paperless lehnt das je nach Feld ab.
def rf($f; $map; $kind):
  if has($f) then .[$f] |= one($map; $kind) else . end;

# Feld mit Listenwert auflösen.
def rl($f; $map; $kind):
  if has($f) then .[$f] |= (if type == "array" then map(one($map; $kind)) else . end)
  else . end;

del(._kommentar)
| .triggers |= map(
    rl("filter_has_tags";                 $tags;   "Tag")
    | rl("filter_has_all_tags";           $tags;   "Tag")
    | rl("filter_has_not_tags";           $tags;   "Tag")
    | rf("filter_has_document_type";      $dts;    "Dokumenttyp")
    | rl("filter_has_any_document_types"; $dts;    "Dokumenttyp")
    | rl("filter_has_not_document_types"; $dts;    "Dokumenttyp")
    | rf("filter_has_storage_path";       $sps;    "Speicherpfad")
    | rl("filter_has_any_storage_paths";  $sps;    "Speicherpfad")
    | rl("filter_has_not_storage_paths";  $sps;    "Speicherpfad")
    | rf("filter_has_correspondent";      $corrs;  "Korrespondent")
    | rl("filter_has_any_correspondents"; $corrs;  "Korrespondent")
    | rl("filter_has_not_correspondents"; $corrs;  "Korrespondent")
  )
| .actions |= map(
    rl("assign_tags";              $tags;   "Tag")
    | rl("remove_tags";            $tags;   "Tag")
    | rf("assign_document_type";   $dts;    "Dokumenttyp")
    | rl("remove_document_types";  $dts;    "Dokumenttyp")
    | rf("assign_storage_path";    $sps;    "Speicherpfad")
    | rl("remove_storage_paths";   $sps;    "Speicherpfad")
    | rl("assign_custom_fields";   $cfs;    "Custom Field")
    | rl("remove_custom_fields";   $cfs;    "Custom Field")
    | rf("assign_correspondent";   $corrs;  "Korrespondent")
    | rl("remove_correspondents";  $corrs;  "Korrespondent")
    | rf("assign_owner";           $users;  "Nutzer")
    | rl("remove_owners";          $users;  "Nutzer")
    | rl("assign_view_users";      $users;  "Nutzer")
    | rl("assign_change_users";    $users;  "Nutzer")
    | rl("remove_view_users";      $users;  "Nutzer")
    | rl("remove_change_users";    $users;  "Nutzer")
    | rl("assign_view_groups";     $groups; "Gruppe")
    | rl("assign_change_groups";   $groups; "Gruppe")
    | rl("remove_view_groups";     $groups; "Gruppe")
    | rl("remove_change_groups";   $groups; "Gruppe")
    # assign_custom_fields_values ist ein Objekt, dessen SCHLÜSSEL die
    # Custom-Field-IDs sind. Nicht-numerische Schlüssel werden als Feldname
    # aufgelöst und wieder zu einem String gemacht (JSON-Objektschlüssel).
    | (if (.assign_custom_fields_values | type) == "object" then
         .assign_custom_fields_values |= with_entries(
           .key |= (if test("^[0-9]+$") then .
                    else (($cfs[.] // error("Unbekannt (Custom Field): " + .)) | tostring)
                    end))
       else . end)
  )
