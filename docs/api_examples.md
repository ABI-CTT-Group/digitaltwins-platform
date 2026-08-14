# Populating SEEK via the API

Worked `curl` examples for creating (and deleting) SEEK objects — programmes,
projects, and on down the ISA hierarchy — using a SEEK API token.

For platform diagnostics (Airflow/Celery queues, docker, TLS, redis, apt), see the
companion cookbook: [`diagnostics.md`](diagnostics.md). See also
[`seek-integration.md`](seek-integration.md) for how the platform itself
authenticates to SEEK and what it can see, and [`populating_data.md`](populating_data.md)
for the UI-based workflow.

## Setup

Everything comes from the deployment's own config — nothing hardcoded:

- `SEEK_API_TOKEN` lives in the **rendered `.env`** (runtime dir), written there by
  `util/generate-token.sh`.
- `PLATFORM_DOMAIN` / `PLATFORM_PROTOCOL` are gen-env **inputs**, so they live in
  the `data/env` file — not the rendered `.env` (which only has them baked inside
  derived URLs).

Point the examples at SEEK through the **gateway** (`<protocol>://<domain>/seek`),
not a direct container port:

```
ENV_FILE=${ENV_FILE:-$HOME/digitaltwins-platform/.env}   # rendered platform .env
DATA_ENV=${DATA_ENV:-/mnt/install_src/data/env}          # gen-env input (domain/protocol)

SEEK_API_TOKEN=$(grep -E '^SEEK_API_TOKEN=' "$ENV_FILE" | cut -d= -f2-)
PLATFORM_PROTOCOL=$(grep -E '^PLATFORM_PROTOCOL=' "$DATA_ENV" | cut -d= -f2-)
PLATFORM_DOMAIN=$(grep -E '^PLATFORM_DOMAIN='   "$DATA_ENV" | cut -d= -f2-)

BASE_API_URL=${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}/seek

[ -n "$SEEK_API_TOKEN" ] || { echo "SEEK_API_TOKEN not found in $ENV_FILE"; exit 1; }
```

SEEK's API uses the `Token token=<token>` authorization scheme. (That's SEEK's own
scheme; the platform's `querier.py` uses a `Bearer` header instead — SEEK accepts
both.)

## Create a programme

```
curl -X POST $BASE_API_URL/programmes \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "data": {
      "type": "programmes",
      "attributes": {
        "title": "Hello World",
        "description": "A simple hello world programme"
      }
    }
  }'
```

Capture the new programme's id for use below:

```
PROGRAMME_ID=$(curl -X POST $BASE_API_URL/programmes \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "data": {
      "type": "programmes",
      "attributes": {
        "title": "Hello World",
        "description": "A simple hello world programme"
      }
    }
  }' | jq -r '.data.id')
```

## Create a project (under a programme)

A project links to its programme(s) via a `relationships` block. Build the body
with the captured `PROGRAMME_ID`, then POST it:

```
TFILE=/tmp/tmp.$$.json
cat > $TFILE <<EOF
{
  "data": {
    "type": "projects",
    "attributes": { "title": "Hello Project" },
    "relationships": {
      "programmes": {
        "data": [ { "id": "$PROGRAMME_ID", "type": "programmes" } ]
      }
    }
  }
}
EOF

curl -X POST $BASE_API_URL/projects \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  --data @$TFILE
```

The same pattern extends down the ISA hierarchy — investigations link to projects,
studies to investigations, assays to studies — each via a `relationships` block
referencing the parent's id.

## Delete

```
# Delete a project
PROJECT_ID=1
curl -X DELETE $BASE_API_URL/projects/$PROJECT_ID \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Accept: application/json"

# Delete a programme
PROGRAMME_ID=1
curl -X DELETE $BASE_API_URL/programmes/$PROGRAMME_ID \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Accept: application/json"
```
