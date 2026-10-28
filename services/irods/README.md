# iRODS (inactive)

A placeholder for an iRODS data store. The folder holds only a `.gitkeep`.

## Purpose

The `digitaltwins` package can store and fetch datasets in iRODS as well as MinIO:
`services/api/src/digitaltwins/irods/`. That code runs only when `IRODS_ENABLED` is true.

## Status

Inactive. There is no compose file, the root `docker-compose.yml` doesn't mention iRODS, and the
`IRODS_*` variables are commented out in `.env.template`. The API's compose file doesn't pass
`IRODS_ENABLED`, so the iRODS code is off in the running platform.

The folder is kept as a placeholder. Removing it is listed in
[docs/future_refactoring.md](../../docs/future_refactoring.md).
