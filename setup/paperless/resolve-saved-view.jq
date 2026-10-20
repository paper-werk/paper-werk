# Übersetzt eine gespeicherte Ansicht aus saved_views.json von NAMEN in die IDs
# der Zielinstanz. Wird von apply.sh per `jq -f` geladen (ausgelagert, damit die
# Auflösung ohne laufende Paperless-Instanz testbar bleibt).
#
# Erwartet die Name->ID-Maps als --argjson: tags, dts, sps, cfs, corrs, users.
# Eingabe: eine einzelne Ansicht. Ausgabe: dieselbe, POST-fertig.
#
# Anders als bei Arbeitsabläufen steht der Bezug hier NICHT im Feldnamen: eine
# Filterregel ist immer nur {"rule_type": N, "value": "..."}, und erst der
# Regeltyp verrät, ob "value" ein Tag, ein Dokumenttyp oder etwas ganz anderes
# ist (bei Typ 0 z. B. schlicht ein Suchbegriff). Die Zuordnung unten stammt aus
# SavedViewFilterRule.RULE_TYPES, ausgelesen aus Paperless 3.0.5.
#
# Rückwärtskompatibel: aufgelöst wird nur, was NICHT rein numerisch ist -
# "value": "2" geht unverändert durch, "value": "Rechnung" wird übersetzt.
# Regeltypen ohne Objektbezug bleiben grundsätzlich unangetastet.
#
# NICHT aufgelöst wird Regeltyp 42 ("custom fields query"): dort steckt die
# Feld-ID in einem serialisierten JSON-String, nicht in einem eigenen Feld -
# dieselbe Einschränkung wie bei filter_custom_field_query in
# resolve-workflow.jq. Solche Ansichten brauchen nach dem Einspielen eine
# Korrektur in der Paperless-Oberfläche.

def kind_of($t):
  if   [6, 17, 22]     | index($t) then "Tag"
  elif [3, 26, 27]     | index($t) then "Korrespondent"
  elif [4, 28, 29]     | index($t) then "Dokumenttyp"
  elif [25, 30, 31]    | index($t) then "Speicherpfad"
  elif [32, 33, 34, 35]| index($t) then "Nutzer"
  elif [38, 39, 40, 41]| index($t) then "Custom Field"
  else null end;

def map_of($kind):
  { "Tag":           $tags,
    "Korrespondent": $corrs,
    "Dokumenttyp":   $dts,
    "Speicherpfad":  $sps,
    "Nutzer":        $users,
    "Custom Field":  $cfs }[$kind];

# "show_in_sidebar" ist eine Absicht für apply.sh und kein Feld der API:
# Seit Paperless 3.x steht die Sichtbarkeit in den UI-Einstellungen des
# Nutzers, nicht an der Ansicht. Im POST-Body würde DRF es stillschweigend
# verwerfen; hier fliegt es deshalb ausdrücklich heraus.
del(._kommentar, .show_in_sidebar, .show_on_dashboard)

# "owner" darf als Benutzername dastehen. Ohne owner ordnet Paperless die
# Ansicht dem Token-Inhaber zu, für Einzelplatz-Installationen das Richtige.
| (if (.owner | type) == "string"
   then .owner = ($users[.owner] // error("Unbekannt (Nutzer): " + .owner))
   else . end)

| .filter_rules |= map(
    kind_of(.rule_type) as $kind
    | if $kind == null
         or (.value | type) != "string"
         or (.value | test("^[0-9]+$"))
      then .
      else .value = ((map_of($kind)[.value]
                      // error("Unbekannt (" + $kind + "): " + .value)) | tostring)
      end
  )
