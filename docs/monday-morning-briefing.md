# Monday Morning Briefing
## Where We Are and What To Do Next

**Written:** Friday 8 May 2026  
**Author:** Claude (Anthropic)  
**For:** The developer who has just had a weekend and needs to remember everything

---

## What We Achieved This Week

You now have a fully working Airflow 3 setup that:

1. **Is proxied behind nginx** at `https://test.digitaltwins.auckland.ac.nz/airflow/` — no separate port, no separate firewall rule, just like all the other services
2. **Integrates with Keycloak SSO** — you log into Airflow with your Keycloak credentials
3. **Exchanges user tokens** — when a portal user triggers a workflow, the API uses their Keycloak identity to call Airflow rather than a shared service account
4. **Runs tasks on a separate compute VM** — the Celery worker is running on a second VM, picking up tasks from the main VM's Redis queue and executing them
5. **Reads and writes MinIO** — the compute worker can reach the main VM's object storage

The end-to-end flow works: portal user triggers assay → digitaltwins-api → Airflow preprocessor DAG → discover subjects → trigger per-subject workflow runs on compute VM.

---

## The One Blocker: VLAN

**This is the first thing to sort on Monday.**

The compute VM is currently failing on the `fetch_assay_configs` task because it can't reach `digitaltwins-api` — that service is only accessible by Docker service name on the main VM's internal network.

The right fix is a **private VLAN between the two VMs**. Email your infrastructure team (University of Auckland ITS or whoever manages the OpenStack/cloud console) and ask for:

> "Can you add a private network interface connecting VM `abi_mp` (130.216.217.182) and the compute VM to the same private VLAN? We need inter-VM communication without going over the public internet."

Once you have private IPs (will look like `10.x.x.x` or `192.168.x.x`), you:
1. Change bind addresses in `.env` from `0.0.0.0` to the private IP
2. Set `MAIN_VM_IP` in the compute worker's `.env` to the main VM's private IP
3. All Docker service name resolution issues go away

**In the meantime** (if you need to keep testing before the VLAN is ready), you can expose the digitaltwins-api port to the compute VM's public IP with a UFW rule — but this is a temporary hack, not a permanent solution.

---

## Current State of Each Service

### Main VM (`abi_mp` — 130.216.217.182)

Everything is running. Access via:
- **Airflow UI:** https://test.digitaltwins.auckland.ac.nz/airflow/
- **Platform API:** https://test.digitaltwins.auckland.ac.nz/api/

The `airflow-worker` service on the main VM is **stopped** (`docker compose stop airflow-worker`) so that the compute VM handles all task execution. If the compute VM is unavailable, restart it with `docker compose start airflow-worker`.

### Compute VM (163.7.144.14)

Running the Celery worker only. Location of files:
- `docker-compose.yml` — worker service definition
- `Dockerfile` — same as `services/airflow/Dockerfile` on main VM
- `.env` — secrets + connection details
- `dags/` — copy of DAGs (must be kept in sync with main VM)
- `logs/` — local task logs (NOT shared with main VM — see issue below)
- `plugins/` — copy of Airflow plugins
- `config/` — copy of Airflow config

**Known issue:** Task logs on the compute VM are not visible in the Airflow UI. The UI says "Error fetching logs. Try number 0 is invalid." To see task logs, SSH into the compute VM and look in the `logs/` directory. This needs a proper fix (see below).

---

## Things That Still Need Fixing

### 1. Task log visibility (medium priority)

When tasks run on the compute VM, their logs are written locally and are not visible in the Airflow UI on the main VM. 

**Fix options:**
- Configure Airflow to use remote logging (write logs to MinIO instead of local filesystem). This is the proper solution — set `AIRFLOW__LOGGING__REMOTE_LOGGING=True` and point it at MinIO.
- Or mount a shared NFS volume for logs between the two VMs.

### 2. DAG synchronisation (medium priority)

The compute VM's `dags/` folder needs to stay in sync with the main VM. Currently manual. 

**Fix:** Set up a git-based sync. The DAGs are in the repo, so a cron job running `git pull` every few minutes on the compute VM would work. Or use Airflow's built-in git bundle support.

### 3. VLAN (high priority — see above)

### 4. Bind addresses (do after VLAN)

Once you have private IPs, change these in the main VM's `.env`:
```
AIRFLOW_BIND_ADDRESS=<private IP>
POSTGRES_BIND_ADDRESS=<private IP>    # platform postgres
AIRFLOW_POSTGRES_BIND_ADDRESS=<private IP>   # airflow postgres
MINIO_BIND_ADDRESS=<private IP>
REDIS_BIND_ADDRESS=<private IP>
```

### 5. Redis password (low priority for now)

Redis has no authentication. Fine on a private VLAN, worth adding before production. Add `requirepass <password>` to Redis config and update `BROKER_URL` in all services.

---

## Port Map

Everything that is or needs to be exposed between VMs:

| Service | Port | Credentials | Status |
|---|---|---|---|
| Airflow API server | 8002 | JWT token | ✅ Open to compute VM |
| Airflow Postgres | 8013 | airflow/airflow | ✅ Open to compute VM |
| Redis | 8016 | none | ✅ Open to compute VM |
| MinIO API | 8011 | minioadmin/minioadmin | ✅ Open to compute VM |
| digitaltwins-api | TBD | Bearer token | ❌ Not yet exposed — BLOCKER |
| Platform Postgres | 8003 | admin/admin | Not needed by worker |

---

## How To Test Everything Is Working

### 1. Get a Keycloak token
```bash
source ~/digitaltwins-platform/.env

TOKEN=$(curl -s -X POST \
  "https://test.digitaltwins.auckland.ac.nz/auth/realms/digitaltwins/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&client_id=${AIRFLOW_KEYCLOAK_CLIENT_ID}&client_secret=${AIRFLOW_KEYCLOAK_CLIENT_SECRET}&username=mp1&password=YOUR_PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### 2. Exchange it for an Airflow token
```bash
AF_TOKEN=$(curl -s -X POST \
  "https://test.digitaltwins.auckland.ac.nz/airflow/keycloak/exchange" \
  -H "Authorization: Bearer ${TOKEN}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### 3. Trigger the test DAG
```bash
curl -s -X POST "https://test.digitaltwins.auckland.ac.nz/airflow/api/v2/dags/test_hello/dagRuns" \
  -H "Authorization: Bearer ${AF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"logical_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
```

### 4. Watch the compute worker pick it up
```bash
# SSH into compute VM
docker compose logs airflow-worker -f
```

### 5. Check task logs on compute VM if something fails
```bash
find logs/ -name "*.log" -newer logs/ | xargs tail -50
```

---

## Important Files Changed This Week

All of these are in the repo on your local machine at `/Users/mpes457/twins/digitaltwins-platform/`:

| File | What changed |
|---|---|
| `buildout/dev/nginx.conf` | Added `/airflow/` proxy location |
| `services/airflow/docker-compose.yml` | BASE_URL, proxy fix, JWT secrets, Keycloak creds, Redis + Airflow Postgres ports |
| `services/airflow/config/webserver_config.py` | Keycloak OIDC, role mapping, hairpin NAT fix |
| `services/airflow/plugins/keycloak_token_exchange.py` | Token exchange endpoint |
| `services/api/digitaltwins-api/app/routers/workflow.py` | User token forwarding |
| `services/api/digitaltwins-api/src/digitaltwins/airflow/workflow.py` | Same, library version |

Full technical documentation is in `docs/airflow-keycloak-integration.md`.

---

## Key Things That Caught Us Out (Don't Repeat These)

1. **nginx proxy_pass trailing slash** — must NOT have a trailing slash. `proxy_pass http://airflow-apiserver:8080;` not `http://airflow-apiserver:8080/;` — the trailing slash strips the `/airflow/` prefix and breaks everything.

2. **Hairpin NAT** — from inside Docker you cannot reach the VM's own public IP. Keycloak back-channel calls in `webserver_config.py` must use `http://keycloak:8080` not the external URL.

3. **Airflow plugin routing** — in Airflow 3, new endpoints MUST use `fastapi_root_middlewares`, not `fastapi_apps` or Flask blueprints. The SPA catch-all route swallows everything else.

4. **JWT format** — Airflow 3 uses HS512 (not HS256), signs with `AIRFLOW__API_AUTH__JWT_SECRET` (not `AIRFLOW__API__SECRET_KEY`), and requires `"aud": "apache-airflow"` in the token.

5. **DAGs are paused at creation** — `DAGS_ARE_PAUSED_AT_CREATION=true` is set. New DAGs won't run until you toggle them on in the UI.

6. **AIRFLOW_ENDPOINT must include the path** — `http://airflow-apiserver:8080/airflow` not just `http://airflow-apiserver:8080`. Even on the internal port, Airflow expects the full path.

7. **Two Postgres instances** — the platform has its own Postgres on port 8003 (`admin/admin`, database `digitaltwins`). Airflow has its own separate Postgres (internal only, now also on port 8013, `airflow/airflow`, database `airflow`). They are completely separate.

8. **Compute worker logs directory** — must exist and be writable before starting: `mkdir -p logs && chmod 777 logs`.

---

## Monday Morning Checklist

- [ ] Email infrastructure team about VLAN
- [ ] While waiting: if you need to test, expose digitaltwins-api port with UFW rule to compute VM IP
- [ ] Sync DAGs to compute VM if any changed over the weekend: `git pull` on compute VM
- [ ] Check compute worker is still running: `docker compose ps` on compute VM
- [ ] Check main VM worker is still stopped: `docker compose ps airflow-worker` on main VM

Have a good weekend.
