# OCR und LLM: verworfene Alternativen

Zwei Wege, die als eigene Compose-Stacks ausprobiert und verworfen wurden:
ein lokales LLM über Ollama und paperless-gpt mit Google Document AI. Der
Stack nutzt Tesseract für OCR und Mistral in der Cloud
(`PAPERLESS_AI_ENABLED=true`, `PAPERLESS_AI_LLM_MODEL=mistral-medium-3-5`).

## Lokales LLM

Gemessen auf einem Jetson Orin Nano:

| Modell | Befund |
|---|---|
| `qwen3:4b` | zu langsam |
| `qwen2.5:3b` | brauchbar |
| `gemma3:2b` | brauchbar |

Auf dieser Hardware tragen Modelle mit rund drei Milliarden Parametern. Das
reicht für einfache Titel- und Tag-Vorschläge, nicht für die Feld- und
Vertragserkennung der Workflows. Deshalb ruft der Stack Mistral in der Cloud.
Bei aktiver KI gehen damit Textauszüge an Mistral, was DSGVO und
Auftragsverarbeitung berührt. Eine Installation ohne Cloud-Kontakt braucht
ein lokales Modell, dessen Größe die Hardware bestimmt.

Ollama lässt sich als weiterer Dienst ergänzen: ein Container, ein Volume,
das Modell per `docker exec -it ollama ollama pull <modell>`.

## Google Document AI als OCR

Tesseract stößt bei schlechten Scans, Handschrift und Tabellen an Grenzen.
`paperless-gpt` kann Document AI als OCR-Anbieter davorschalten. Wird das
gebraucht, gehört `paperless-gpt` als weiterer Dienst in
`compose/docker-compose.yml` oder eine `compose.override.yml`.

* **Processor und Region müssen zusammenpassen.** In der Google Cloud Console
  einen Document-AI-Processor anlegen (z. B. „Document OCR“); Processor-ID
  und Region gehören in die Konfiguration. Eine unpassende Region führt zu
  Fehlermeldungen, die nicht auf die Region hinweisen.
* **Zugang über einen Service Account** mit der Rolle *Document AI API
  User*, JSON-Key auf dem Server und nur lesend in den Container gemountet.
  `gcloud auth application-default login` ist für Arbeitsplätze gedacht.
* **`PDF_REPLACE=true` löscht das Original** und ersetzt das eingescannte
  Dokument durch die OCR-Fassung. Bei aufbewahrungspflichtigen Belegen nicht
  setzen.
* Zum Ausprobieren `OCR_LIMIT_PAGES=5` setzen, um Kosten bei einem großen
  Stapel zu begrenzen.
