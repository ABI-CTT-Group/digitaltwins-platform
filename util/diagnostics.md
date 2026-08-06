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
