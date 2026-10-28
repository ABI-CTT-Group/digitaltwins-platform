# Pretend external PACS

A test stand-in for a hospital PACS outside the platform: one Orthanc instance that `orthanc-1` can
exchange studies with.

## Purpose

It plays an external PACS (AE title `radiaology`, display name "Radiaology PACS") with `orthanc-1` as
its DICOM peer, for testing transfers into the platform's PACS. Unlike `services/pacs`, its
`orthanc.json` has no de-identification plugin.

## Status

Inactive. Its include in the root `docker-compose.yml` is commented out, marked as for testing only
and to be disabled for production.

It is kept for PACS testing. It publishes host ports 8042 and 4242, and it needs `services/pacs` and
Keycloak running on the same network. Removing or archiving it is listed in
[docs/future_refactoring.md](../../docs/future_refactoring.md).

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | `pacs-pretend-external` and its authorisation service |
| `Dockerfile` | The same image as `services/pacs/Dockerfile` |
| `orthanc.json` | A copy of `services/pacs/orthanc.json` with the name and the peer changed and the plugin removed |
| `permissions.json` | Identical to `services/pacs/permissions.json` |
