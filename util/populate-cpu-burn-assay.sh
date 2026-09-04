#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# populate-cpu-burn-assay.sh — create a full SEEK Programme -> Project ->
# Investigation -> Study -> Assay chain ("CPU Burn ..."), register a real
# sample dataset, and configure the assay so clicking "Run" in the portal
# launches services/airflow/dags/workflow_9000.py on the remote compute node.
#
# Authenticates as the platform admin via a Keycloak PASSWORD grant (client
# "api", direct access grants enabled) -- NOT client_credentials, which hits a
# service account that owns/sees nothing. This way the created content is
# owned by, and visible to, a real person in the portal.
#
# SEEK object creation requires ACTIVE PROJECT MEMBERSHIP for everything
# nested under it (investigation/study/assay) -- an API-created project does
# NOT enrol its creator automatically, so this adds the admin as a member
# (via util/add-seek-project-member.sh, addressed by their pinned Keycloak
# sub) immediately after creating the project, before creating anything else.
#
# The dataset is the repo's own SPARC SDS fixture
# (services/api/digitaltwins-api/tests/data/example_sds_dataset.zip) --
# its samples.xlsx has sample_type "DCE-MRI Contrast Image sam-1" for
# sub-1/sub-2's sam-1 rows (exact string match in Postgres; see
# src/digitaltwins/postgres/querier.py get_dataset_samples), which is what
# the assay's `inputs[].sample_type` below must match verbatim.
#
# workflow_seek_id 9000 is not a real SEEK Workflow -- it is never validated
# by SEEK, only used to name the DAG (workflow_9000). Its ONLY job is to
# match services/airflow/dags/workflow_9000.py's dag_id.
#
# Run from the repo root on the portal host (needs docker compose for the
# add-seek-project-member.sh step). Idempotent it is NOT -- re-running
# creates a second "CPU Burn ..." chain; this is a one-shot setup script.
#
# Usage:
#   ./util/populate-cpu-burn-assay.sh
#     Requires PLATFORM_ADMIN_PASSWORD and KEYCLOAK_CLIENT_SECRET already in
#     the environment, e.g.:
#       set -a; . /mnt/install_src/data/secrets.env; set +a
#       ./util/populate-cpu-burn-assay.sh
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_DIR="${BASE_DIR:-$HOME/digitaltwins-platform}"
cd "$BASE_DIR"

: "${PLATFORM_ADMIN_PASSWORD:?set PLATFORM_ADMIN_PASSWORD (source secrets.env first)}"
: "${KEYCLOAK_CLIENT_SECRET:?set KEYCLOAK_CLIENT_SECRET (source secrets.env first)}"

ENV_FILE="$BASE_DIR/.env"
PROT=$(grep -E '^PLATFORM_PROTOCOL='     "$ENV_FILE" | cut -d= -f2-)
DOM=$(grep  -E '^PLATFORM_DOMAIN='       "$ENV_FILE" | cut -d= -f2-)
# .env.template maps the unified PLATFORM_ADMIN_USERNAME input onto the legacy
# AIRFLOW_USERNAME key for backward compat with existing consumers -- there is
# no literal "PLATFORM_ADMIN_USERNAME=" line in the rendered runtime .env.
ADMIN_U=$(grep -E '^AIRFLOW_USERNAME=' "$ENV_FILE" | cut -d= -f2-)
[ -n "$PROT" ] && [ -n "$DOM" ] && [ -n "$ADMIN_U" ] || { echo "populate-cpu-burn-assay: PLATFORM_PROTOCOL/DOMAIN/AIRFLOW_USERNAME missing from $ENV_FILE" >&2; exit 1; }

# The platform's own public domain does not resolve from the portal host itself
# (confirmed live 2026-09-04 -- a pure DNS gap, not a gateway health issue) --
# --resolve pins it to loopback without needing a real hosts-file/DNS fix.
RESOLVE_PORT=80; [ "$PROT" = https ] && RESOLVE_PORT=443
CURL_OPTS=(--resolve "${DOM}:${RESOLVE_PORT}:127.0.0.1")
[ "$PROT" = https ] && CURL_OPTS+=(-k)

BASE="$PROT://$DOM"
SEEK_BASE="$BASE/seek"
DTAPI_BASE="$BASE/digitaltwins-api"

echo "populate-cpu-burn-assay: authenticating as $ADMIN_U (password grant, client=api)"
TOKEN=$(curl -s "${CURL_OPTS[@]}" -X POST "$BASE/auth/realms/digitaltwins/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=api -d client_secret="$KEYCLOAK_CLIENT_SECRET" \
  -d username="$ADMIN_U" -d password="$PLATFORM_ADMIN_PASSWORD" -d scope=openid \
  | jq -r '.access_token // empty')
[ -n "$TOKEN" ] || { echo "populate-cpu-burn-assay: failed to get a token -- check PLATFORM_ADMIN_PASSWORD/KEYCLOAK_CLIENT_SECRET" >&2; exit 1; }

seek_post() {  # $1 = resource type (programmes/projects/...), $2 = JSON:API body -> prints the new id
  local resp id
  resp=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/vnd.api+json" \
    -X POST "$SEEK_BASE/$1" -d "$2")
  id=$(echo "$resp" | jq -r '.data.id // empty')
  if [ -z "$id" ]; then
    echo "populate-cpu-burn-assay: failed creating $1:" >&2
    echo "$resp" >&2
    exit 1
  fi
  echo "$id"
}

echo "== creating SEEK Programme/Project/Investigation/Study/Assay =="
PROG_ID=$(seek_post programmes '{"data":{"type":"programmes","attributes":{"title":"CPU Burn Programme"}}}')
echo "  Programme #$PROG_ID"

PROJ_ID=$(seek_post projects "$(jq -n --arg pid "$PROG_ID" '{data:{type:"projects",attributes:{title:"CPU Burn Project"},relationships:{programme:{data:{type:"programmes",id:$pid}}}}}')")
echo "  Project #$PROJ_ID"

echo "== adding platform admin as a member of the new project (required before creating anything under it) =="
REALM_TEMPLATE="services/keycloak/digitaltwins-realm.json.template"
ADMIN_SUB=$(grep -A1 '"id":' "$REALM_TEMPLATE" | grep -B1 'PLATFORM_ADMIN_USERNAME' | grep '"id":' | head -1 | sed -E 's/.*"id": *"([^"]+)".*/\1/')
[ -n "$ADMIN_SUB" ] || { echo "populate-cpu-burn-assay: could not find the platform admin's pinned id in $REALM_TEMPLATE" >&2; exit 1; }
./util/add-seek-project-member.sh "sub:$ADMIN_SUB" "$PROJ_ID" -y

INV_ID=$(seek_post investigations "$(jq -n --arg proj "$PROJ_ID" '{data:{type:"investigations",attributes:{title:"CPU Burn Investigation"},relationships:{projects:{data:[{type:"projects",id:$proj}]}}}}}')")
echo "  Investigation #$INV_ID"

STUDY_ID=$(seek_post studies "$(jq -n --arg inv "$INV_ID" '{data:{type:"studies",attributes:{title:"CPU Burn Study"},relationships:{investigation:{data:{type:"investigations",id:$inv}}}}}}')")
echo "  Study #$STUDY_ID"

ASSAY_ID=$(seek_post assays "$(jq -n --arg study "$STUDY_ID" '{data:{type:"assays",attributes:{title:"CPU Burn Assay",tags:["script"],assay_class:{key:"EXP"},assay_type:{uri:"http://jermontology.org/ontology/JERMOntology#Experimental_assay_type"},technology_type:{uri:"http://jermontology.org/ontology/JERMOntology#Technology_type"}},relationships:{study:{data:{type:"studies",id:$study}}}}}}')")
echo "  Assay #$ASSAY_ID"

echo "== registering the example SDS dataset fixture =="
FIXTURE_ZIP="services/api/digitaltwins-api/tests/data/example_sds_dataset.zip"
[ -f "$FIXTURE_ZIP" ] || { echo "populate-cpu-burn-assay: fixture not found: $FIXTURE_ZIP" >&2; exit 1; }
DATASET_UUID=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" \
  -X POST "$DTAPI_BASE/datasets?category=measurements" \
  -F "files=@${FIXTURE_ZIP};type=application/zip;filename=example_sds_dataset.zip" \
  | jq -r '.dataset_uuid // empty')
[ -n "$DATASET_UUID" ] || { echo "populate-cpu-burn-assay: dataset registration failed" >&2; exit 1; }
echo "  dataset_uuid=$DATASET_UUID"

echo "== configuring the assay (digitaltwins-api Postgres record) =="
CONFIG_BODY=$(jq -n --argjson assay_seek_id "$ASSAY_ID" --arg dataset_uuid "$DATASET_UUID" '{
  assay_seek_id: $assay_seek_id,
  workflow_seek_id: 9000,
  cohort: ["1", "2"],
  ready: true,
  inputs: [{name: "input", category: "measurements", dataset_uuid: $dataset_uuid, sample_type: "DCE-MRI Contrast Image sam-1"}],
  outputs: [{name: "primes_output", category: "measurements", dataset_name: "cpu_burn_primes_output", sample_name: "primes"}]
}')
curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$DTAPI_BASE/assays" -d "$CONFIG_BODY" | jq .

cat <<EOF

populate-cpu-burn-assay: done.

Before triggering:
  1. Sync the DAG to the compute node:  ./util/sync-compute-dags.sh <compute-node>
  2. Make sure a worker actually serves the "remote" queue (WORKER_QUEUES=remote
     on the compute node's .env, generated by util/generate-compute-env.sh).

Trigger: open the CPU Burn Assay (#$ASSAY_ID) in the portal and click Run. It
fans out one DAG run per discovered sample (2, from sub-1/sub-2's sam-1 rows).

Watch it happen: Airflow UI (workflow_9000 task logs) and Grafana (remote
node's CPU climbing for ~60s per run).

View the result in Jupyter -- open a notebook and read straight from MinIO
(same bucket/prefix the portal's own "download results" button uses):

  import boto3, os
  s3 = boto3.client("s3", endpoint_url=os.environ["MINIO_ENDPOINT"],
                    aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
                    aws_secret_access_key=os.environ["MINIO_SECRET_KEY"])
  # list what landed under assay_$ASSAY_ID/ to find the exact run prefix, then:
  # s3.get_object(Bucket="airflow-workspace", Key="<prefix>/primes.txt")["Body"].read().decode()

EOF
