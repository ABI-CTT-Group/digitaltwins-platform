#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# populate-isa-mock-assays.sh: register the mock workflows in
# examples/workflow/workflow_mock_* and create the "Breast pilot mockups"
# SEEK study with one configured assay per mock step of the ISA breast pilot
# (Assays 3, 5, 6, 7 and 9). The mocks only wait, so a demo can launch, monitor
# and submit them like real assays.
#
# What it creates, as the platform admin:
#   - 4 SEEK workflows (+ their tools), registered through the platform API in
#     SEEK_PROJECT_ID; the 2 script workflows' DAGs deploy automatically.
#   - study "Breast pilot mockups" in SEEK_INVESTIGATION_ID, visible to the project.
#   - 5 assays in that study, each linked to its workflow (an SOP) and
#     configured with fixed input datasets and cohort ["1"].
# Re-running creates everything again (a second study and new workflows).
#
# Inputs (existing datasets; each needs samples for subject 1):
#   NIFTI_DATASET_UUID    measurement dataset with sample type "nifti"
#   MODELS_DATASET_UUID   model dataset (only its uuid is passed to the DAG)
#   CURATED_DATASET_UUID  measurement dataset with sample type "pre"
# Ids default to the Test Project (project 12, investigation 10).
#
# Authenticates like populate-cpu-burn-assay.sh: a Keycloak password grant as
# the platform admin (AIRFLOW_USERNAME in .env).
#
# Usage, from the repo root on the portal host:
#   set -a; . ./secrets.env; set +a     # PLATFORM_ADMIN_PASSWORD, KEYCLOAK_CLIENT_SECRET
#   NIFTI_DATASET_UUID=... MODELS_DATASET_UUID=... CURATED_DATASET_UUID=... \
#     ./util/populate-isa-mock-assays.sh
# Prints the new SEEK assay ids; put them in the portal's ISA link table
# (services/portal/frontend/src/views/isa-project/platformRun.ts).
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_DIR="${BASE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$BASE_DIR"

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
SEEK_PROJECT_ID="${SEEK_PROJECT_ID:-12}"
SEEK_INVESTIGATION_ID="${SEEK_INVESTIGATION_ID:-10}"
STUDY_TITLE="${STUDY_TITLE:-Breast pilot mockups}"

: "${PLATFORM_ADMIN_PASSWORD:?set PLATFORM_ADMIN_PASSWORD (source secrets.env first)}"
: "${KEYCLOAK_CLIENT_SECRET:?set KEYCLOAK_CLIENT_SECRET (source secrets.env first)}"
: "${NIFTI_DATASET_UUID:?set NIFTI_DATASET_UUID (a measurement dataset with nifti samples)}"
: "${MODELS_DATASET_UUID:?set MODELS_DATASET_UUID (a model dataset)}"
: "${CURATED_DATASET_UUID:?set CURATED_DATASET_UUID (a measurement dataset with pre samples)}"

log() { echo "populate-isa-mock-assays: $*" >&2; }
die() { log "$*"; exit 1; }

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
SEEK_BASE="$BASE/seek"
DTAPI_BASE="$BASE/api"

log "authenticating as $ADMIN_U"
TOKEN=$(curl -s "${CURL_OPTS[@]}" -X POST "$BASE/auth/realms/digitaltwins/protocol/openid-connect/token" \
  --data-urlencode grant_type=password --data-urlencode client_id=api \
  --data-urlencode client_secret="$KEYCLOAK_CLIENT_SECRET" --data-urlencode username="$ADMIN_U" \
  --data-urlencode password="$PLATFORM_ADMIN_PASSWORD" --data-urlencode scope=openid \
  | jq -r '.access_token // empty')
[ -n "$TOKEN" ] || die "failed to get a token: check PLATFORM_ADMIN_PASSWORD/KEYCLOAK_CLIENT_SECRET"

seek_post() {  # $1 = resource type, $2 = JSON:API body -> prints the new id
  local resp id
  resp=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.api+json" -H "Content-Type: application/vnd.api+json" \
    -X POST "$SEEK_BASE/$1" -d "$2")
  id=$(echo "$resp" | jq -r '.data.id // empty')
  [ -n "$id" ] || die "failed creating $1: $resp"
  echo "$id"
}

register_workflow() {  # $1 = package folder name, $2 = workflow type -> prints the SEEK workflow id
  local dir="examples/workflow/$1" zip resp id
  [ -d "$dir" ] || die "package not found: $dir"
  zip="$(mktemp -d)/$1.zip"
  (cd examples/workflow && zip -qr "$zip" "$1")
  resp=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" \
    -X POST "$DTAPI_BASE/datasets?category=workflows&workflow_type=$2&seek_project_id=$SEEK_PROJECT_ID" \
    -F "files=@${zip};type=application/zip;filename=$1.zip")
  rm -rf "$(dirname "$zip")"
  id=$(echo "$resp" | jq -r '.seek_id // empty')
  [ -n "$id" ] || die "registering $1 failed: $resp"
  echo "$id"
}

create_assay() {  # $1 = title, $2 = type tag -> prints the new assay id
  seek_post assays "$(jq -n --arg study "$STUDY_ID" --arg title "$1" --arg tag "$2" '{data:{type:"assays",
    attributes:{title:$title,tags:[$tag],assay_class:{key:"EXP"},
      assay_type:{uri:"http://jermontology.org/ontology/JERMOntology#Experimental_assay_type"},
      technology_type:{uri:"http://jermontology.org/ontology/JERMOntology#Technology_type"}},
    relationships:{study:{data:{type:"studies",id:$study}}}}}')"
}

configure_assay() {  # $1 = assay id, $2 = workflow id, $3 = inputs JSON, $4 = outputs JSON
  local body resp
  body=$(jq -n --argjson assay "$1" --argjson wf "$2" --argjson inputs "$3" --argjson outputs "$4" \
    '{assay_seek_id:$assay, workflow_seek_id:$wf, cohort:["1"], ready:true, link_workflow:true,
      inputs:$inputs, outputs:$outputs}')
  resp=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -X POST "$DTAPI_BASE/assays" -d "$body")
  echo "$resp" | jq -e '.assay_uuid' >/dev/null || die "configuring assay $1 failed: $resp"
}

input() {  # $1 = name, $2 = dataset uuid, $3 = sample type, $4 = category
  jq -n --arg n "$1" --arg d "$2" --arg s "$3" --arg c "$4" '{name:$n,dataset_uuid:$d,sample_type:$s,category:$c}'
}
outputs() {  # $1 = dataset name, $2... = output names
  local ds="$1"; shift
  printf '%s\n' "$@" | jq -R --arg ds "$ds" '{name:., dataset_name:$ds, sample_name:., category:"measurements"}' | jq -s .
}

log "registering the mock workflows in SEEK project $SEEK_PROJECT_ID"
WF_INFERENCE=$(register_workflow workflow_mock_inference script)
WF_BREAST_MODEL=$(register_workflow workflow_mock_breast_model script)
WF_FINETUNING=$(register_workflow workflow_mock_model_finetuning notebook)
WF_STATISTICS=$(register_workflow workflow_mock_statistical_analysis notebook)
log "  workflows: inference #$WF_INFERENCE, breast model #$WF_BREAST_MODEL, fine-tuning #$WF_FINETUNING, statistics #$WF_STATISTICS"

STUDY_ID=$(seek_post studies "$(jq -n --arg inv "$SEEK_INVESTIGATION_ID" --arg title "$STUDY_TITLE" \
  '{data:{type:"studies",attributes:{title:$title},relationships:{investigation:{data:{type:"investigations",id:$inv}}}}}')")
log "  study #$STUDY_ID: $STUDY_TITLE"

A3=$(create_assay "Mock Assay 3: initial inference" script)
A5=$(create_assay "Mock Assay 5: model fine-tuning" notebook)
A6=$(create_assay "Mock Assay 6: inference" script)
A7=$(create_assay "Mock Assay 7: generate breast model" script)
A9=$(create_assay "Mock Assay 9: statistical analysis" notebook)

# API-created items default to private; make them visible to the project, as the SEEK UI would.
log "setting the study and assay policies to visible-to-project"
docker compose exec -T -e "PROJ_ID=$SEEK_PROJECT_ID" -e "IDS=$STUDY_ID $A3 $A5 $A6 $A7 $A9" \
  "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
proj = Project.find(ENV.fetch('PROJ_ID'))
study_id, *assay_ids = ENV.fetch('IDS').split
[Study.find(study_id), *assay_ids.map { |id| Assay.find(id) }].each do |item|
  Seek::Permissions::Authorization.disable_authorization_checks do
    item.policy = Policy.projects_policy([proj])
    item.save!(validate: false)
  end
end
RUBY

log "configuring the assays"
NIFTI=$(input mri_nifti "$NIFTI_DATASET_UUID" nifti measurements)
MODELS=$(for m in skin outer_rib sternum lesion; do input "${m}_model" "$MODELS_DATASET_UUID" "" models; done | jq -s .)
INFERENCE_INPUTS=$(jq -n --argjson a "$NIFTI" --argjson b "$MODELS" '[$a] + $b')
SEGMENTATIONS=(skin_inference_nifti outer_rib_inference_nifti sternum_inference_nifti lesion_inference_nifti)

configure_assay "$A3" "$WF_INFERENCE" "$INFERENCE_INPUTS" "$(outputs mock_initial_inference "${SEGMENTATIONS[@]}")"
configure_assay "$A6" "$WF_INFERENCE" "$INFERENCE_INPUTS" "$(outputs mock_inference "${SEGMENTATIONS[@]}")"
configure_assay "$A7" "$WF_BREAST_MODEL" \
  "$(for s in "${SEGMENTATIONS[@]:0:3}"; do input "$s" "$NIFTI_DATASET_UUID" nifti measurements; done | jq -s .)" \
  "$(outputs mock_breast_model point_cloud breast_mesh)"
configure_assay "$A5" "$WF_FINETUNING" \
  "$(input clinician_validated_masks "$CURATED_DATASET_UUID" pre measurements | jq -s .)" \
  "$(outputs finetuned_models finetuned_models)"
configure_assay "$A9" "$WF_STATISTICS" \
  "$(input lesion_position_reports "$CURATED_DATASET_UUID" pre measurements | jq -s .)" \
  "$(outputs statistics_summary statistics_summary)"

cat <<EOF

populate-isa-mock-assays: done. New SEEK assays in study #$STUDY_ID ("$STUDY_TITLE"):
  Assay 3 initial inference     #$A3   (script, workflow #$WF_INFERENCE)
  Assay 5 model fine-tuning     #$A5   (notebook, workflow #$WF_FINETUNING)
  Assay 6 inference             #$A6   (script, workflow #$WF_INFERENCE)
  Assay 7 generate breast model #$A7   (script, workflow #$WF_BREAST_MODEL)
  Assay 9 statistical analysis  #$A9   (notebook, workflow #$WF_STATISTICS)

The script workflows' DAGs (workflow_$WF_INFERENCE, workflow_$WF_BREAST_MODEL) deploy in the
background; they show in Airflow within a minute or two.
EOF
