# Deployment Variants — Bind Address Guide

This document explains the three deployment configurations and how bind
addresses should be set for each. The relevant `.env` variables are:

```
DIGITALTWINS_API_BIND_ADDRESS
MINIO_BIND_ADDRESS
AIRFLOW_BIND_ADDRESS
POSTGRES_BIND_ADDRESS
REDIS_BIND_ADDRESS
AIRFLOW_POSTGRES_BIND_ADDRESS
```

Services that are **never** directly reachable from outside Docker
(keycloak, orthanc, portal-backend, hapi-fhir) are always `127.0.0.1`
regardless of deployment variant.

---

## Variant 1: Single VM, internal compute only

All Celery workers run inside Docker on the same VM. No external process
needs to reach postgres, redis, airflow, or minio directly.

**Bind addresses:** `127.0.0.1` for all services above.

Services are reachable within Docker via container DNS (`database`,
`redis`, `minio`, etc.) — no host-level exposure needed.

```
DIGITALTWINS_API_BIND_ADDRESS=127.0.0.1
MINIO_BIND_ADDRESS=127.0.0.1
AIRFLOW_BIND_ADDRESS=127.0.0.1
POSTGRES_BIND_ADDRESS=127.0.0.1
REDIS_BIND_ADDRESS=127.0.0.1
AIRFLOW_POSTGRES_BIND_ADDRESS=127.0.0.1
```

---

## Variant 2: VLAN compute (e.g. compute2 on 10.2.0.x)

A separate VM on the same private VLAN runs Celery workers. It needs to
reach postgres, redis, airflow, and minio on the platform VM directly over
the VLAN.

**Bind addresses:** the platform VM's VLAN IP (e.g. `10.2.0.195`).

Security is provided by the VLAN itself — only machines on the same
private network can reach these ports.

```
DIGITALTWINS_API_BIND_ADDRESS=10.2.0.195
MINIO_BIND_ADDRESS=10.2.0.195
AIRFLOW_BIND_ADDRESS=10.2.0.195
POSTGRES_BIND_ADDRESS=10.2.0.195
REDIS_BIND_ADDRESS=10.2.0.195
AIRFLOW_POSTGRES_BIND_ADDRESS=10.2.0.195
```

---

## Variant 3: External compute (public Internet)

A remote VM (e.g. a cloud instance) runs Celery workers and must reach
back to the platform VM over the public Internet.

**Bind addresses:** `0.0.0.0` (bind to all interfaces, including the
public-facing one).

**Security is entirely the responsibility of the cloud security group /
firewall rules.** The ports for postgres (8003), redis (8016), airflow
(8002), and minio (9000/9001) must be restricted to allow traffic **only
from the remote compute node's IP address**. Without this, these services
are exposed to the open Internet.

```
DIGITALTWINS_API_BIND_ADDRESS=0.0.0.0
MINIO_BIND_ADDRESS=0.0.0.0
AIRFLOW_BIND_ADDRESS=0.0.0.0
POSTGRES_BIND_ADDRESS=0.0.0.0
REDIS_BIND_ADDRESS=0.0.0.0
AIRFLOW_POSTGRES_BIND_ADDRESS=0.0.0.0
```

---

## .env.template default

The `.env.template` defaults to Variant 3 (`0.0.0.0`) because the current
`abi_portal` deployment has an external compute node on the public Internet.
This is the most permissive setting — it works for all three variants but
requires the firewall/security group to be correctly configured for
Variants 2 and 3.

For a single-VM deployment with no external compute, change all six
addresses to `127.0.0.1` after the ansible run.

---

## Port reference

| Service | Port | Used by compute |
|---|---|---|
| PostgreSQL | 8003 | Airflow workers (metadata DB) |
| Redis | 8016 | Celery broker |
| Airflow API | 8002 | Workers registering results |
| MinIO | 9000 | Workers storing output data |
