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

The rest of the ISA hierarchy follows the same shape — each object links to its
parent via a `relationships` block. Capture each new id with `| jq -r '.data.id'`
(as shown for the programme) to feed the next level. Note the relationship name and
cardinality differ per level: project→`programmes` and investigation→`projects` are
**to-many** (arrays); study→`investigation` and assay→`study` are **to-one**
(single objects).

## Create an investigation (under a project)

```
cat > $TFILE <<EOF
{
  "data": {
    "type": "investigations",
    "attributes": { "title": "Hello Investigation" },
    "relationships": {
      "projects": { "data": [ { "id": "$PROJECT_ID", "type": "projects" } ] }
    }
  }
}
EOF

INVESTIGATION_ID=$(curl -sX POST $BASE_API_URL/investigations \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  --data @$TFILE | jq -r '.data.id')
```

## Create a study (under an investigation)

```
cat > $TFILE <<EOF
{
  "data": {
    "type": "studies",
    "attributes": { "title": "Hello Study" },
    "relationships": {
      "investigation": { "data": { "id": "$INVESTIGATION_ID", "type": "investigations" } }
    }
  }
}
EOF

STUDY_ID=$(curl -sX POST $BASE_API_URL/studies \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  --data @$TFILE | jq -r '.data.id')
```

## Create an assay (under a study)

Assays carry two extra requirements beyond a title + parent `study`: an
**`assay_class`** (`EXP` = experimental, `MOD` = modelling), and — for experimental
assays — an **assay type** and **technology type** (ontology term URIs). The exact
required attributes vary by SEEK version, so if a POST 422s, **`GET` an existing
assay** and mirror its `attributes`/`relationships` (see "Exporting for re-import"
below).

```
cat > $TFILE <<EOF
{
  "data": {
    "type": "assays",
    "attributes": {
      "title": "Hello Assay",
      "assay_class": { "key": "EXP" }
    },
    "relationships": {
      "study": { "data": { "id": "$STUDY_ID", "type": "studies" } }
    }
  }
}
EOF

ASSAY_ID=$(curl -sX POST $BASE_API_URL/assays \
  -H "Authorization: Token token=$SEEK_API_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  --data @$TFILE | jq -r '.data.id')
```

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

## Exporting for re-import (dumping into another environment)

There is **no one-button "dump the whole hierarchy to a re-POSTable file"** in
SEEK. But the JSON:API **GET** responses are nearly the same shape as the POST
bodies above, so you can roll your own export→replay:

```
# The GET shape is close to the POST shape — fetch an item and keep just the
# fields you'd re-POST (strip server-managed id / links / meta / timestamps):
curl -s -H "Authorization: Token token=$SEEK_API_TOKEN" -H "Accept: application/json" \
  $BASE_API_URL/studies/$STUDY_ID | jq '{data: (.data | {type, attributes, relationships})}'
```

To move content to another environment, walk the hierarchy **top-down**
(programmes → projects → investigations → studies → assays), and for each item
GET it, strip the server-managed fields, and POST it into the target — **remapping
the parent id** to the id the target returned for that parent.

Two caveats decide whether this is worth it vs. a wholesale copy:

- **ID remapping is mandatory.** Ids differ per environment, so every
  `relationships` reference must be rewritten from the source id to the target's
  new id as you go. (Keep a source-id → target-id map as you replay.)
- **These POSTs move metadata only.** The actual data — **data files, samples,
  SOPs, models** — lives in SEEK's filestore/MinIO, not in these JSON bodies. A
  metadata replay creates empty shells; the blobs move separately.

So pick the tool for the job:

- **Full environment clone** → `util/stage-dump.sh` → `util/portal-restore.sh`
  copies SEEK's entire DB **and** filestore in one shot (see `../util/README.md`).
  DB-level, so it also brings users/tokens — no ID remapping, but not selective.
- **Selective, API-native metadata migration** → the GET→remap→POST replay above,
  using this doc's POST bodies as the target shape.
- **Standards-based** → SEEK can export an Investigation as **ISA-JSON** and some
  assets as **RO-Crate** (portable archives), but re-import of those is via SEEK's
  own import, not these simple POSTs.
