# Diagnostics cookbook

Proven "how do I check X" commands for the platform, grouped by area. Companion to
[`api_examples.txt`](api_examples.txt) (which is SEEK REST API create/delete examples).

**Run these from the platform repo dir** (e.g. `~/digitaltwins-platform`) so
`docker compose` resolves the project + `COMPOSE_FILE` from `.env`. Read-only
unless noted.

---

## Airflow / Celery — task routing & workers

The Celery inspect commands share a long prefix; set it once:

```bash
CEL="celery --app airflow.providers.celery.executors.celery_executor.app"
```

**Who's connected, to which queues?** (the key one for remote-compute — a node
serving `remote` shows `celery@<host> -> remote`; the portal's local worker shows
`default`):
```bash
docker compose exec airflow-scheduler $CEL inspect active_queues
```

**Which workers are alive right now?**
```bash
docker compose exec airflow-scheduler $CEL inspect ping
```

**What is each worker running / has reserved this moment?**
```bash
docker compose exec airflow-scheduler $CEL inspect active     # executing now
docker compose exec airflow-scheduler $CEL inspect reserved   # prefetched, waiting
docker compose exec airflow-scheduler $CEL inspect stats      # pool size, totals per worker
```

**Where will a DAG's tasks route?** The platform lever is the `compute_queue`
Airflow Variable. Check the value Airflow resolves (env `AIRFLOW_VAR_*` wins over
the metadata DB):
```bash
docker compose exec airflow-scheduler airflow variables get compute_queue
docker compose exec airflow-scheduler printenv AIRFLOW_VAR_COMPUTE_QUEUE
```

**Does a DAG actually read that Variable?** (if it doesn't, setting the var routes
nothing — tasks stay on `default`):
```bash
grep -rn 'Variable.get("compute_queue"' services/airflow/dags/
```

**What DAGs exist / are they paused?**
```bash
docker compose exec airflow-scheduler airflow dags list
docker compose exec airflow-scheduler airflow dags list --output table | grep -i paused
```

**A worker's broker/connection health** (chasing the Redis AUTH / "No host
supplied" class of failures):
```bash
docker compose logs --tail=80 airflow-worker | grep -Ei 'redis|auth|broker|connect|host'
```

---

## Docker / compose — stack state

**Everything's status + published ports:**
```bash
docker compose ps --format '{{.Service}}\t{{.Status}}\t{{.Ports}}'
```

**Is the Redis broker published on the VLAN?** (REMOTE_COMPUTE=true → expect
`0.0.0.0:8005->6379`):
```bash
docker compose ps redis
```

**What value is baked into a running container?** (env is frozen at create-time —
if this is stale, the container predates a `.env` change → `up -d` to recreate):
```bash
docker compose exec <service> printenv <VAR>
```

**What does a container actually have mounted?** (e.g. confirm the gateway's cert /
acme-webroot binds):
```bash
GW=$(docker compose ps -q gateway)
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' "$GW"
```

---

## TLS / gateway cert

**Expiry of the deployed cert** (what the gateway reads):
```bash
openssl x509 -in services/nginx/certs/server.crt -noout -subject -issuer -enddate
```

**Cert as actually served on 443** (use a timeout — `s_client` can hang):
```bash
echo | timeout 5 openssl s_client -connect localhost:443 -servername <domain> 2>/dev/null \
  | openssl x509 -noout -subject -enddate
```

**Is renewal automated?** (`disabled` timer + no cron ⇒ NOT automatic):
```bash
systemctl list-timers | grep -i certbot
systemctl is-enabled certbot.timer
```

**Is the ACME challenge path served over http?** (webroot renewal prerequisite —
want `404`, i.e. the acme location is active and NOT redirected to https; a `301`
means the redirect is winning):
```bash
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: <domain>' \
  http://127.0.0.1/.well-known/acme-challenge/does-not-exist
```

---

## Deploy / config

**Preview what a runtime sync would change** (itemized — an empty list = in sync):
```bash
util/sync-runtime.sh -n
```

**Key deploy values as rendered into `.env`:**
```bash
grep -E '^(PLATFORM_DOMAIN|SSL|NGINX_MODE|SSL_CERT_DIR|REMOTE_COMPUTE|AIRFLOW_VAR_COMPUTE_QUEUE)=' .env
```

**Do all the secrets in `secrets.env` exist in the template?** (keys only — no
values printed):
```bash
comm -23 \
  <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' secrets.env          | sed 's/=$//' | LC_ALL=C sort -u) \
  <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' secrets.env.template  | sed 's/=$//' | LC_ALL=C sort -u)
# output = keys in secrets.env missing from the template (empty = fully covered)
```

---

## apt / packages (airgap installs)

**Package configured, or just unpacked?** (`ii` = installed+configured; `iU` =
unpacked but deps unmet — the airgap `dpkg -i` failure mode):
```bash
dpkg -l | grep -E 'certbot|josepy|acme'
```

---

## SSH hop (portal → node)

The portal's default-deny-outgoing ufw blocks `ssh -J portal node` until you allow
outbound 22 to the node (ON THE PORTAL):
```bash
sudo ufw status verbose                                    # check Default: outgoing
sudo ufw allow out to <node_vlan_ip> port 22 proto tcp
```

---

# Troubleshooting by symptom

Real failures hit on this platform and the commands that made them legible. DB
access idioms used below (run from the repo dir):
```bash
# Platform Postgres (digitaltwins/hapi):
docker compose exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "…"'
# SEEK MySQL (programmes/projects/…):  note: unset MYSQL_HOST so mysql uses the socket
docker compose exec -T db sh -c 'unset MYSQL_HOST; mysql -u root -p"$MYSQL_ROOT_PASSWORD" seek -t -e "…"'
```

## Portal shows "no programmes" / "couldn't load this level" / 504
Usually **SEEK is still booting** (slow Rails/Puma), often right after a stack
recreate — NOT a real break. A blanket `docker compose up -d` that bounced SEEK is
the common trigger (do scoped recreates instead).
```bash
docker compose ps                                        # is seek healthy or still starting?
docker compose logs --tail=50 seek | grep -i "listening" # wait for "Listening on http://0.0.0.0:2000"
# rule out a DB restart/OOM/too-many-connections underneath:
docker compose logs --tail=30 database | grep -iE "shutdown|restart|fatal|too many|out of memory|ready to accept"
```
Fix: wait for SEEK to finish booting; recreate services scoped, never blanket.

## Assay launches (API returns 200) but nothing appears in Airflow
`run_assay` swallows a missing-DAG 404 into a 200. The child `workflow_<seek_id>`
DAG usually **doesn't exist, is paused, or the dags/ folder is empty** (DAGs aren't
in the bundle).
```bash
# 1. map the assay -> the workflow DAG it will trigger
docker compose exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT assay_seek_id, assay_uuid, workflow_seek_id, cohort, ready FROM assay ORDER BY assay_seek_id;"'
# 2. does workflow_<seek_id> actually exist / parse?
docker compose exec -T airflow-scheduler airflow dags list
docker compose exec -T airflow-scheduler airflow dags list-import-errors
# 3. is it paused / has it ever run?
docker compose exec -T airflow-scheduler airflow dags details  <dag_id> | grep -i is_paused
docker compose exec -T airflow-scheduler airflow dags list-runs <dag_id>
```
Fix: `sync-dags` the DAG to the box, wait ~1 min for the dag-processor, **un-pause**
(new DAGs boot paused).

**Marry an assay to where it lives in the SEEK GUI** (programme→project→
investigation→study) — handy for support:
```bash
docker compose exec -T db sh -c 'unset MYSQL_HOST; mysql -u root -p"$MYSQL_ROOT_PASSWORD" seek -t -e "
 SELECT a.id AS assay_id, a.title AS assay, pr.title AS programme, p.title AS project,
        i.title AS investigation, s.title AS study
 FROM assays a
 LEFT JOIN studies s               ON s.id = a.study_id
 LEFT JOIN investigations i        ON i.id = s.investigation_id
 LEFT JOIN investigations_projects ip ON ip.investigation_id = i.id
 LEFT JOIN projects p              ON p.id = ip.project_id
 LEFT JOIN programmes pr           ON pr.id = p.programme_id
 ORDER BY a.id;"' | grep -v "Using a password"
```

## DAGs "launched" in the GUI but never reach the Airflow dashboard (fresh/rebuilt box)
Empty dags/ folder, a wrong dag-processor mount, or a dag-processor startup race.
```bash
find services/airflow/dags -type f | head            # empty => no DAG files (sync-dags)
# what the dag-processor SEES vs the host path actually mounted there:
docker compose exec -T airflow-dag-processor ls -la /opt/airflow/dags
docker inspect $(docker compose ps -q airflow-dag-processor) \
  --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' | grep -i dags
docker compose logs --tail=25 airflow-dag-processor    # parse/startup errors
```

## Tasks stuck `queued` forever (remote-compute)
Either no worker serves the target queue, or the **Redis broker auth is
mismatched** (broker URL carries `REDIS_PASSWORD` but base Redis wasn't started
with `--requirepass` — the old override-gated bug), often because a stale
`~/.bashrc` `export COMPOSE_FILE` overrode `.env` and dropped the override.
```bash
grep '^COMPOSE_FILE=' .env                             # does it include the override?
grep -n COMPOSE_FILE ~/.bashrc || echo "(none - good)" # a stale export here overrides .env
echo "${COMPOSE_FILE:-(unset in shell)}"
docker inspect $(docker compose ps -q redis) --format '{{.Args}}'   # is --requirepass present?
docker compose config | awk '/^  redis:/{f=1} f&&/command:/{print; exit}'  # merged redis command
# then confirm a worker actually serves the queue (see Airflow/Celery section):
docker compose exec airflow-scheduler $CEL inspect active_queues
```

## `COMPOSE_FILE` change "isn't taking"
Precedence gotchas: a shell `export` beats `.env`; non-interactive shells don't
read `~/.bashrc`.
```bash
grep -n COMPOSE_FILE ~/.bashrc            # legacy home for it (now lives in .env)
bash -lc 'echo COMPOSE_FILE=$COMPOSE_FILE'
grep '^COMPOSE_FILE=' .env
```

## `sync-runtime` deleted airflow.cfg / a generated file
`services/airflow/config/airflow.cfg` is regenerated by airflow-init (`airflow
config list`), not hand-edited — settings come from `AIRFLOW__*` env vars. It's now
excluded from sync; if you see it deleted, it regenerates within seconds:
```bash
ls -la services/airflow/config/           # airflow.cfg present again?
docker compose ps | grep -i airflow       # stack still healthy (no restart)?
```

## Where does task routing even come from?
```bash
# any task hardcoding a queue, or reading the compute_queue Variable?
grep -rnE "queue\s*=|Variable.get\(\"compute_queue\"" --include=*.py services/airflow/dags/
```
