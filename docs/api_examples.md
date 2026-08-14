# Populating SEEK via the API

Worked `curl` examples for creating (and deleting) SEEK objects — programmes,
projects, and on down the ISA hierarchy — using a SEEK API token.

For platform diagnostics (Airflow/Celery queues, docker, TLS, redis, apt), see the
companion cookbook: [`diagnostics.md`](diagnostics.md). See also
[`seek-integration.md`](seek-integration.md) for how the platform itself
authenticates to SEEK and what it can see, and [`populating_data.md`](populating_data.md)
for the UI-based workflow.

## Setup

Read the API token (written by `util/generate-token.sh` to
`~/keys/seek_api_token.txt`) and point at SEEK. These examples hit SEEK
**directly** on port 8001, not via the `/seek` gateway route:

```
SEEK_TOKEN_FILE_NAME=${SEEK_TOKEN_FILE_NAME:=~/keys/seek_api_token.txt}
IP=$(curl -s ifconfig.me)
BASE_API_URL=http://${IP}:8001

[[ -f "$SEEK_TOKEN_FILE_NAME" ]] || { echo "No seek token file: $SEEK_TOKEN_FILE_NAME"; exit 1; }
SEEK_API_TOKEN=$(<"$SEEK_TOKEN_FILE_NAME") || exit 1
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
