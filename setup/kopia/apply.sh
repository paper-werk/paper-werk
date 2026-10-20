#!/usr/bin/env bash
# Richtet Kopia ein: Repository verbinden/anlegen (externe Disk oder
# Backblaze B2), Default-Backup-Policy setzen, ersten Snapshot ziehen.
#
# Voraussetzung: Der kopia-Container des Projekt-Stacks läuft und hat
# KOPIA_PASSWORD in seiner Umgebung (.env.kopia); das Skript selbst
# bekommt das Repository-Passwort nie zu sehen.
#
# Idempotent: Ist bereits ein Repository verbunden, wird dieser Schritt
# übersprungen; Policy-Set und Snapshot sind gefahrlos wiederholbar.

set -euo pipefail
cd "$(dirname "$0")/.."
source lib/common.sh
load_conf
require_cmd docker

docker inspect "$KOPIA_CONTAINER" >/dev/null 2>&1 \
  || die "Kopia-Container '$KOPIA_CONTAINER' nicht gefunden (KOPIA_CONTAINER in setup.conf prüfen)"

# MSYS_NO_PATHCONV nur für diesen Aufruf: kopia-Argumente sind reine
# Container-Pfade (/repository, /source/...), die Git Bash sonst in
# Windows-Pfade umschreiben würde.
kexec() { MSYS_NO_PATHCONV=1 docker exec "$KOPIA_CONTAINER" kopia "$@"; }

# ── 1. Repository ────────────────────────────────────────────────────────────
if kexec repository status >/dev/null 2>&1; then
  log "Repository bereits verbunden - übersprungen."
else
  repo_type="${KOPIA_REPO_TYPE:-}"
  if [ -z "$repo_type" ]; then
    echo "Wohin soll gesichert werden?"
    echo "  1) disk - lokales Repository-Volume (z. B. externe Platte)"
    echo "  2) s3   - Cloud (Backblaze B2 über den S3-kompatiblen Endpunkt)"
    # Ohne Terminal (Skriptlauf, CI, aktualisieren.sh) liest read sofort EOF,
    # und der Lauf endete ohne Meldung mit Code 1, weil die Frage nicht
    # beantwortet werden konnte.
    [ -t 0 ] || die "KOPIA_REPO_TYPE ist in setup.conf nicht gesetzt, und hier ist kein Terminal, das antworten könnte. Bitte KOPIA_REPO_TYPE=disk oder =s3 eintragen."
    read -rp "Auswahl [1/2]: " answer
    case "$answer" in
      1) repo_type=disk ;;
      2) repo_type=s3 ;;
      *) die "Ungültige Auswahl." ;;
    esac
  fi

  case "$repo_type" in
    disk)
      # /repository ist im Compose-File das Volume kopia-repository. Für eine
      # externe Platte /repository per compose.override.yml auf sie legen.
      log "Lege Filesystem-Repository unter /repository an …"
      kexec repository connect filesystem --path=/repository 2>/dev/null \
        || kexec repository create filesystem --path=/repository
      ;;
    s3)
      [ -n "${S3_BUCKET:-}" ] && [ -n "${S3_ENDPOINT:-}" ] \
        && [ -n "${S3_ACCESS_KEY:-}" ] && [ -n "${S3_SECRET_KEY:-}" ] \
        || die "Für s3 müssen S3_BUCKET, S3_ENDPOINT, S3_ACCESS_KEY und S3_SECRET_KEY in setup.conf gesetzt sein."
      log "Verbinde S3-Repository (Bucket: $S3_BUCKET, Endpunkt: $S3_ENDPOINT) …"
      kexec repository connect s3 \
        --bucket="$S3_BUCKET" --endpoint="$S3_ENDPOINT" \
        --access-key="$S3_ACCESS_KEY" --secret-access-key="$S3_SECRET_KEY" 2>/dev/null \
        || kexec repository create s3 \
             --bucket="$S3_BUCKET" --endpoint="$S3_ENDPOINT" \
             --access-key="$S3_ACCESS_KEY" --secret-access-key="$S3_SECRET_KEY"
      warn "Zugangsdaten (Bucket, Endpunkt, Key-ID, Secret) zusätzlich extern sichern -"
      warn "sie stehen nur in der Kopia-Config und sind im Disaster-Fall weg!"
      warn ""
      warn "BEI BACKBLAZE B2 ZUSÄTZLICH IM WEB-UI PRÜFEN:"
      warn "  1. Bucket -> Lifecycle Settings -> 'Keep only the last version of the file'."
      warn "     Default ist 'Keep all versions' - dann bleiben ALLE von Kopia gelöschten"
      warn "     Blobs als versteckte Versionen liegen und zählen weiter aufs Kontingent."
      warn "  2. Application Key auf genau dieses Bucket beschränken, Capabilities nur"
      warn "     listBuckets, listFiles, readFiles, writeFiles, deleteFiles"
      warn "     sowie readFileRetentions, writeFileRetentions für Object Lock."
      warn "     Den Key PER API anlegen: 'Read and Write' im Web-UI vergibt 25"
      warn "     Capabilities inklusive bypassGovernance - und die hebelt Object"
      warn "     Lock aus, der Key darf dann trotz Sperre löschen."
      warn "  3. Object Lock lässt sich nur BEIM ANLEGEN des Buckets aktivieren,"
      warn "     nachträglich nicht mehr. Danach im Repository einschalten mit"
      warn "     kopia repository set-parameters --retention-mode=GOVERNANCE \\"
      warn "       --retention-period=7d"
      warn "  Alle drei erklärt: docs/object-lock.md (Ablauf, Kosten, Verifikation),"
      warn "  Hintergrund zum Backup selbst: docs/kopia-backblaze.md"
      ;;
    b2)
      # Kopias b2-Provider ist deprecated; nur noch für Altinstallationen.
      # Umstellung auf s3: docs/kopia-backblaze.md, "Neuverbindung".
      [ -n "${B2_BUCKET:-}" ] && [ -n "${B2_KEY_ID:-}" ] && [ -n "${B2_KEY:-}" ] \
        || die "Für b2 müssen B2_BUCKET, B2_KEY_ID und B2_KEY in setup.conf gesetzt sein."
      warn "KOPIA_REPO_TYPE=b2 ist veraltet - Kopias b2-Provider wird entfernt werden."
      warn "Für Neuinstallationen s3 verwenden (gleiches Bucket, anderer Zugriffsweg)."
      log "Verbinde Backblaze-B2-Repository (Bucket: $B2_BUCKET) …"
      kexec repository connect b2 \
        --bucket="$B2_BUCKET" --key-id="$B2_KEY_ID" --key="$B2_KEY" 2>/dev/null \
        || kexec repository create b2 \
             --bucket="$B2_BUCKET" --key-id="$B2_KEY_ID" --key="$B2_KEY"
      warn "B2-Zugangsdaten (Bucket, Key-ID, Key) zusätzlich extern sichern -"
      warn "sie stehen nur in der Kopia-Config und sind im Disaster-Fall weg!"
      ;;
    *) die "Unbekannter KOPIA_REPO_TYPE: $repo_type (erlaubt: disk, s3, b2)" ;;
  esac
  ok "Repository verbunden."
fi

# ── 2. Default-Backup-Policy ─────────────────────────────────────────────────
policy_args=(--compression=zstd --snapshot-time="$KOPIA_SNAPSHOT_TIME")
while read -r rule; do
  rule="${rule//$'\r'/}"
  case "$rule" in ''|\#*) continue ;; esac
  policy_args+=(--add-ignore="$rule")
done <"$PROJECT_DIR/einstellungen/kopia/ignore.rules"

log "Setze Backup-Policy für $KOPIA_SOURCE_PATH (zstd, täglich $KOPIA_SNAPSHOT_TIME) …"
kexec policy set "$KOPIA_SOURCE_PATH" "${policy_args[@]}" >/dev/null
ok "Policy gesetzt."

# ── 3. Erster Snapshot ───────────────────────────────────────────────────────
log "Ziehe initialen Snapshot von $KOPIA_SOURCE_PATH (kann dauern) …"
kexec snapshot create "$KOPIA_SOURCE_PATH"
ok "Kopia eingerichtet - Zeitplan läuft ab jetzt täglich um $KOPIA_SNAPSHOT_TIME."
