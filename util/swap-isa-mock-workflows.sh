#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# swap-isa-mock-workflows.sh: move the ISA breast pilot's mock assays, created
# by an older populate-isa-mock-assays.sh, onto the renamed workflows, so
# nothing a demo audience sees says "mock". The assays keep their SEEK ids, so
# the portal's ISA link table (platformRun.ts) doesn't change.
#
#   1. Registers examples/workflow/workflow_{breast_inference,breast_model,
#      model_finetuning,statistical_analysis} through the platform API, unless
#      a workflow of that name is already registered.
#   2. Re-saves each assay's configuration (as the portal's config dialog does)
#      with the new workflow and the output datasets' "mock_" prefix dropped.
#   3. Retitles the assays ("Mock Assay 3: initial inference" becomes
#      "3. Initial inference") and their study ("Breast pilot mockups" becomes
#      "Te Whatu Ora Breast Pilot") in SEEK.
#   4. Destructive, asks first unless -y: deletes the SEEK SOPs that linked
#      the assays to the old workflows, the old workflow_mock_* workflows with
#      their tools (Postgres, MinIO, SEEK, FHIR, Airflow DAG folder), and the
#      submitted mock_* output datasets.
#
# Re-running is safe: each step skips what is already done.
#
# Usage, from the repo root on the portal host:
#   set -a; . ./secrets.env; set +a     # PLATFORM_ADMIN_PASSWORD, KEYCLOAK_CLIENT_SECRET
#   ./util/swap-isa-mock-workflows.sh [-n] [-y]
#     -n   dry run: print what would change, change nothing
#     -y   delete without asking
# ASSAY_IDS (default "46 47 48 49 50") names the mock assays; SEEK_PROJECT_ID
# (default 12) is where the new workflows are registered.
# ---------------------------------------------------------------------------
set -euo pipefail

DRY_RUN=0; YES=0
while getopts "ny" opt; do
  case "$opt" in n) DRY_RUN=1 ;; y) YES=1 ;; *) exit 2 ;; esac
done

BASE_DIR="${BASE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$BASE_DIR"

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
SEEK_PROJECT_ID="${SEEK_PROJECT_ID:-12}"
ASSAY_IDS="${ASSAY_IDS:-46 47 48 49 50}"
STUDY_TITLE="Te Whatu Ora Breast Pilot"
OLD_STUDY_TITLE="Breast pilot mockups"

: "${PLATFORM_ADMIN_PASSWORD:?set PLATFORM_ADMIN_PASSWORD (source secrets.env first)}"
: "${KEYCLOAK_CLIENT_SECRET:?set KEYCLOAK_CLIENT_SECRET (source secrets.env first)}"

log() { echo "swap-isa-mock-workflows: $*" >&2; }
die() { log "$*"; exit 1; }
run() { if [ "$DRY_RUN" = 1 ]; then log "  (dry run) $*"; return 1; fi; }  # false in a dry run
confirm() {  # $1 = question; true when the deletion should go ahead
  [ "$DRY_RUN" = 1 ] && { log "  (dry run) would ask: $1"; return 1; }
  [ "$YES" = 1 ] && return 0
  if ! (: </dev/tty) 2>/dev/null; then log "  no terminal to ask \"$1\"; skipped (pass -y to delete)"; return 1; fi
  local answer=""; read -r -p "$1 [y/N] " answer </dev/tty
  [ "$answer" = y ] || [ "$answer" = Y ]
}

ENV_FILE="$BASE_DIR/.env"
PROT=$(grep -E '^PLATFORM_PROTOCOL=' "$ENV_FILE" | cut -d= -f2-)
DOM=$(grep -E '^PLATFORM_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)
ADMIN_U=$(grep -E '^AIRFLOW_USERNAME=' "$ENV_FILE" | cut -d= -f2-)
[ -n "$PROT" ] && [ -n "$DOM" ] && [ -n "$ADMIN_U" ] || die "PLATFORM_PROTOCOL/DOMAIN/AIRFLOW_USERNAME missing from $ENV_FILE"

# The platform's public domain may not resolve from the host itself; pin it to loopback.
RESOLVE_PORT=80; [ "$PROT" = https ] && RESOLVE_PORT=443
CURL_OPTS=(--resolve "${DOM}:${RESOLVE_PORT}:127.0.0.1")
[ "$PROT" = https ] && CURL_OPTS+=(-k)
BASE="$PROT://$DOM"
DTAPI_BASE="$BASE/api"

log "authenticating as $ADMIN_U"
TOKEN=$(curl -s "${CURL_OPTS[@]}" -X POST "$BASE/auth/realms/digitaltwins/protocol/openid-connect/token" \
  --data-urlencode grant_type=password --data-urlencode client_id=api \
  --data-urlencode client_secret="$KEYCLOAK_CLIENT_SECRET" --data-urlencode username="$ADMIN_U" \
  --data-urlencode password="$PLATFORM_ADMIN_PASSWORD" --data-urlencode scope=openid \
  | jq -r '.access_token // empty')
[ -n "$TOKEN" ] || die "failed to get a token: check PLATFORM_ADMIN_PASSWORD/KEYCLOAK_CLIENT_SECRET"

api() {  # $1 = method, $2 = path, then curl args -> prints the body; dies on an HTTP error
  local method="$1" path="$2"; shift 2
  local out code
  out=$(curl -s "${CURL_OPTS[@]}" -w '\n%{http_code}' -H "Authorization: Bearer $TOKEN" -X "$method" "$DTAPI_BASE$path" "$@")
  code=${out##*$'\n'}; out=${out%$'\n'*}
  [ "${code:0:1}" = 2 ] || die "$method $path failed ($code): $out"
  echo "$out"
}

seek_ruby() {  # stdin = Ruby; runs in the SEEK container with authorization checks off
  docker compose exec -T "$@" "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
}

# Old package -> new package.
declare -A RENAMED=(
  [workflow_mock_inference]=workflow_breast_inference
  [workflow_mock_breast_model]=workflow_breast_model
  [workflow_mock_model_finetuning]=workflow_model_finetuning
  [workflow_mock_statistical_analysis]=workflow_statistical_analysis
)
declare -A TYPE=(
  [workflow_breast_inference]=script [workflow_breast_model]=script
  [workflow_model_finetuning]=notebook [workflow_statistical_analysis]=notebook
)

datasets() { api GET "/datasets?categories=$1" | jq -c '.datasets[] | {uuid: .dataset_uuid, name: .dataset_name, seek_id}'; }

# --- 1. register the renamed workflows ---------------------------------------
declare -A NEW_ID OLD_NAME_BY_ID
WORKFLOWS=$(datasets workflows)
for old in "${!RENAMED[@]}"; do
  id=$(jq -r --arg n "$old" 'select(.name == $n) | .seek_id' <<<"$WORKFLOWS" | head -n1)
  [ -n "$id" ] && OLD_NAME_BY_ID[$id]=$old
done
for new in "${RENAMED[@]}"; do
  id=$(jq -r --arg n "$new" 'select(.name == $n) | .seek_id' <<<"$WORKFLOWS" | head -n1)
  if [ -n "$id" ]; then
    log "$new is already registered (#$id)"
  elif run "register $new (${TYPE[$new]})"; then
    zip="$(mktemp -d)/$new.zip"
    (cd examples/workflow && zip -qr "$zip" "$new")
    id=$(api POST "/datasets?category=workflows&workflow_type=${TYPE[$new]}&seek_project_id=$SEEK_PROJECT_ID" \
      -F "files=@${zip};type=application/zip;filename=$new.zip" | jq -r '.seek_id // empty')
    rm -rf "$(dirname "$zip")"
    [ -n "$id" ] || die "registering $new returned no seek_id"
    log "registered $new as #$id"
  fi
  NEW_ID[$new]=$id
done

# --- 2. re-save each assay on its new workflow ------------------------------
STUDY_IDS=()
for assay in $ASSAY_IDS; do
  body=$(api GET "/assays/$assay?get_configs=true")
  STUDY_IDS+=("$(jq -r '.assay.relationships.study.data.id // empty' <<<"$body")")
  wf=$(jq -r '.assay.configs.workflow_seek_id' <<<"$body")
  old=${OLD_NAME_BY_ID[$wf]:-}
  if [ -z "$old" ]; then log "assay #$assay already runs workflow #$wf"; continue; fi
  new=${RENAMED[$old]}
  run "re-save assay #$assay: $old (#$wf) -> $new" || continue
  jq --argjson wf "${NEW_ID[$new]}" '.assay.configs | {assay_uuid, assay_seek_id, workflow_seek_id: $wf, cohort, ready,
      inputs: [.inputs[] | del(.assay_uuid)],
      outputs: [.outputs[] | del(.assay_uuid) | .dataset_name |= sub("^mock_"; "")],
      link_workflow: true}' <<<"$body" \
    | api POST /assays -H "Content-Type: application/json" -d @- >/dev/null
  log "assay #$assay now runs $new (#${NEW_ID[$new]})"
done

# --- 3. retitle the assays and their study in SEEK --------------------------
STUDIES=$(printf '%s\n' "${STUDY_IDS[@]}" | sort -u | tr '\n' ' ')
if run "retitle assays $ASSAY_IDS and study $STUDIES"; then
  seek_ruby -e "ASSAYS=$ASSAY_IDS" -e "STUDIES=$STUDIES" -e "TITLE=$STUDY_TITLE" -e "OLD_TITLE=$OLD_STUDY_TITLE" <<'RUBY'
Seek::Permissions::Authorization.disable_authorization_checks do
  ENV.fetch('ASSAYS').split.each do |id|
    a = Assay.find(id)
    next unless (m = a.title.match(/\AMock Assay (\d+): (.+)\z/))
    new = "#{m[1]}. #{m[2][0].upcase}#{m[2][1..]}"
    puts "assay ##{id}: #{a.title} -> #{new}"
    a.title = new
    a.save!(validate: false)
  end
  ENV.fetch('STUDIES').split.each do |id|
    s = Study.find(id)
    next unless s.title == ENV.fetch('OLD_TITLE')
    puts "study ##{id}: #{s.title} -> #{ENV.fetch('TITLE')}"
    s.title = ENV.fetch('TITLE')
    s.save!(validate: false)
  end
end
RUBY
fi

# --- 4. delete the old SOPs, workflows and outputs (destructive) ------------
# The SOPs go first: SEEK cleanup in the platform's delete is best-effort, and a
# workflow a SOP still names could otherwise stay in SEEK.
SOPS=$(seek_ruby -e "OLD_WORKFLOWS=${!OLD_NAME_BY_ID[*]}" <<'RUBY'
old = ENV.fetch('OLD_WORKFLOWS').split
Seek::Permissions::Authorization.disable_authorization_checks do
  Sop.all.select { |s| s.assays.empty? && s.workflows.any? && (s.workflows.map { |w| w.id.to_s } - old).empty? }
     .each { |s| puts "SOP #{s.id} #{s.title}" }
end
RUBY
) || true
SOPS=$(sed -n 's/^SOP //p' <<<"$SOPS")
while read -r sop title; do
  [ -n "$sop" ] || continue
  if confirm "Delete SEEK SOP #$sop ($title), which only links the old workflows and no assay?"; then
    seek_ruby -e "SOP=$sop" <<'RUBY'
Seek::Permissions::Authorization.disable_authorization_checks { Sop.find(ENV.fetch('SOP')).destroy! }
RUBY
    log "deleted SOP #$sop"
  fi
done <<<"$SOPS"

for id in "${!OLD_NAME_BY_ID[@]}"; do
  old=${OLD_NAME_BY_ID[$id]}
  uuid=$(jq -r --arg n "$old" 'select(.name == $n) | .uuid' <<<"$WORKFLOWS" | head -n1)
  if confirm "Delete workflow $old (#$id, $uuid) and its tools?"; then
    api DELETE "/datasets/$uuid?delete_tools=true" >/dev/null
    log "deleted $old"
  fi
done

datasets measurements | jq -c 'select(.name | startswith("mock_"))' | while read -r ds; do
  name=$(jq -r .name <<<"$ds"); uuid=$(jq -r .uuid <<<"$ds")
  if confirm "Delete output dataset $name ($uuid)?"; then
    api DELETE "/datasets/$uuid" >/dev/null
    log "deleted $name"
  fi
done

log "done"
