# Assay Workflow Routing — Merge Notes for Chinchien

## Background

`main_buildout` and `main` diverged on `app/routers/workflow.py` in
`digitaltwins-api`. This document explains what each branch contributed
and how the conflict was resolved, so the merge can be reviewed and
the result ported back to `main` if desired.

---

## What Chinchien's `main` added

**Commit:** `d22b208 feat [assay]: run jupyter assay`

The `run_assay` endpoint gained tag-based dispatch: an assay's SEEK tags
now determine how it is run.

```python
tags = assay.get("assay").get("attributes").get("tags")

if "script" in tags:
    # trigger Airflow preprocessor DAG
    response = _trigger_dag(PREPROCESSOR_DAG_ID, conf)
    ...
    return {"dag_run": ..., "monitor_url": ...}
elif "notebook" in tags:
    # return a JupyterLab URL for the user to open
    monitor_url = f"http://{HOSTNAME}:8008/lab/workspaces/auto-0/tree/work/assays/assay_{assay_id}"
    return {"url": monitor_url}
else:
    raise HTTPException(400, "Assay must have 'script' or 'notebook' tag")
```

The monitor URL for Airflow used the internal `HOSTNAME:AIRFLOW_PORT`
directly.

---

## What `main_buildout` had

Two changes made independently on `main_buildout`:

### 1. User token passthrough (`user_keycloak_token`)

The calling user's Keycloak Bearer token is extracted from the request
and passed to `_trigger_dag`, which attempts to exchange it for a
user-scoped Airflow JWT (via a Keycloak token exchange plugin). This
attributes the DAG run to the actual user in Airflow rather than the
service account.

```python
user_token = bearer_credentials.credentials if bearer_credentials else None
response = _trigger_dag(PREPROCESSOR_DAG_ID, conf, user_keycloak_token=user_token)
```

Falls back silently to the service account if exchange fails.

### 2. Proxy-aware Airflow monitor URL (`AIRFLOW_PUBLIC_URL`)

The abi_portal deployment serves Airflow behind an nginx reverse proxy
at `/airflow/`. Using `HOSTNAME:PORT` produces an internal URL that
doesn't work for users. The fix reads `AIRFLOW_PUBLIC_URL` from the
environment:

```python
monitor_base_url = AIRFLOW_PUBLIC_URL.rstrip('/') if AIRFLOW_PUBLIC_URL \
    else f"http://{HOSTNAME}:{AIRFLOW_EXPOSE_PORT}"
```

`AIRFLOW_PUBLIC_URL` is set to `https://abi1.drai.auckland.ac.nz/airflow`
in `.env`.

---

## Merged result

The merged `main_buildout` combines all three contributions:

1. **Tag-based dispatch** from Chinchien — unchanged logic, `script` vs
   `notebook` vs error.
2. **User token passthrough** — applied to the `script` branch's
   `_trigger_dag` call.
3. **Proxy-aware monitor URL** — applied to the `script` branch's
   `monitor_base_url`.
4. **Notebook URL updated for JupyterHub** — `main` referenced
   JupyterLab directly on port 8008. `main_buildout` replaced JupyterLab
   with JupyterHub (proxied at `/jupyterhub/`), so the notebook URL
   now uses the `JUPYTERHUB_PUBLIC_URL` env var:

```python
jupyterhub_url = os.getenv("JUPYTERHUB_PUBLIC_URL", "").rstrip('/')
monitor_url = f"{jupyterhub_url}/hub/user-redirect/lab/tree/work/assays/assay_{assay_id}"
```

---

## Recommendation for `main`

The user token passthrough and proxy-aware monitor URL are deployment
improvements that should be safe to bring into `main` as well. The
JupyterHub URL change only applies if `main` also adopts JupyterHub
(replacing JupyterLab) — otherwise the original JupyterLab URL is
correct for that branch.
