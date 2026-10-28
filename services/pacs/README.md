# PACS (Orthanc)

Two Orthanc DICOM servers that de-identify every image they receive, each guarded by a Keycloak-backed
authorisation service.

## Purpose

`orthanc-1` and `orthanc-2` store medical images. A Python plugin de-identifies each incoming DICOM
instance before it is written to disk; an instance that fails de-identification is discarded. The two
instances are DICOM peers, so studies can be moved between them. Users browse them in Orthanc Explorer 2
after signing in through Keycloak.

No other platform service calls Orthanc today: the API, the builder, the DAGs and the portal have no
code that talks to it.

## Status

Active. The root `docker-compose.yml` includes this folder's `docker-compose.yml`.

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | `orthanc-1`, `orthanc-2`, and their authorisation services `orthanc-auth-service-1` and `-2` |
| `Dockerfile` | `orthancteam/orthanc` plus `pydicom` and `dicom-anonymizer`, for the plugin |
| `orthanc.json` | Configuration shared by both instances. Per-instance values (`ORTHANC_AET`, `PEER_AET`, `PEER_HOST`, `ORTHANC_AUTH_SERVICE_HOST`) come from each container's environment |
| `permissions.json` | Realm role → Orthanc permissions, read by the authorisation services (`admin`, `clinician`, `researcher`) |
| `scripts/deidentification.py` | The de-identification plugin, mounted into both instances |
| `scripts/on_received_instance_legacy.py` | An older de-identification plugin. Its mount is commented out |
| `tests/` | Manual scripts against a running Orthanc, and synthetic test DICOM files in `tests/testdata/` |

## Connects to

| Peer | How |
|---|---|
| Keycloak | Orthanc Explorer 2 signs users in through the public `orthanc` client at `ORTHANC_KEYCLOAK_URL`. The authorisation services call `http://keycloak:8080/auth` with the realm's `admin-cli` client secret, `ORTHANC_KEYCLOAK_CLIENT_SECRET` |
| Each other | DICOM, as `PEER` in `orthanc.json` (`PEER_AET`, `PEER_HOST`, port 4242) |
| gateway | `/orthanc-1/` and `/orthanc-2/` → port 8042, prefix stripped. The comments in `platform-routes.conf` call these routes best-effort |
| The host | HTTP and DICOM ports per instance (`ORTHANC_1_HTTP_PORT`, `ORTHANC_1_DICOM_PORT`, and the same for `_2`) |

## Configuration

Set in the root `.env` (rendered from `.env.template`); the secrets come from `secrets.env`.

| Variable | Use |
|---|---|
| `ORTHANC_1_HTTP_PORT`, `ORTHANC_1_DICOM_PORT`, `ORTHANC_1_AET` | Instance 1's host ports and DICOM AE title |
| `ORTHANC_2_HTTP_PORT`, `ORTHANC_2_DICOM_PORT`, `ORTHANC_2_AET` | The same for instance 2 |
| `ORTHANC_KEYCLOAK_URL` | Browser-facing Keycloak URL; must equal `KC_HOSTNAME` plus a trailing slash |
| `ORTHANC_KEYCLOAK_CLIENT_SECRET` | Secret of the realm's `admin-cli` client, not of `orthanc` |
| `ORTHANC_AUTH_SECRET_KEY` | Signing key of the authorisation services |
| `ORTHANC_AUTH_SERVICE_PASSWORD` | Password Orthanc uses to call its authorisation service |

## Run & test

No automated tests: nothing here is in `make` or CI. The scripts in `tests/` are manual checks against
a running Orthanc. They default to the host ports in `.env.template`, read `ORTHANC_URL`,
`ORTHANC_USER` and `ORTHANC_PASSWORD` (and `KEYCLOAK_TOKEN_URL` where they sign in), and need
`pydicom` and `requests` (`pynetdicom` for the C-MOVE script). For example:

```bash
python services/pacs/tests/generate_test_dicom.py        # writes tests/testdata/synthetic_phi.dcm
python services/pacs/tests/test_deidentification.py      # uploads it and checks the stored tags
```

Each script's docstring or argument help says what it checks. The scripts that sign in default
`KEYCLOAK_TOKEN_URL` to `http://localhost:8009/realms/...`, without the `/auth` prefix Keycloak
serves under (`KC_HTTP_RELATIVE_PATH`), so set it explicitly.

## Gotchas

- **Changing the plugin file means changing `orthanc.json` too.** `Python.Path` names the mounted
  script.
- **`AuthenticationEnabled` is `false`** in `orthanc.json`. Access control comes from the
  authorisation plugin and the authorisation services, which check the user's realm roles against
  `permissions.json`.
- **Two Keycloak clients, don't cross them.** `orthanc` (public) is for user sign-in; `admin-cli`
  (confidential) is for the authorisation services. See
  [REALM.md](../keycloak/REALM.md#two-orthanc-clients--dont-cross-them).
- **The authorisation services publish `localhost` URLs.** Their `PUBLIC_ORTHANC_ROOT` and
  `PUBLIC_LANDING_ROOT` point at `http://localhost:<port>/`, not at the gateway routes.
- `orthanc-auth-service` publishes amd64 images only; the compose file pins `platform: linux/amd64`.
