# Read the API's environment through one settings module

- **Date:** 2026-11-18
- **Status:** Accepted

## Context

The API and its library (`services/api/app/` and `services/api/src/digitaltwins/`) read environment
variables in about 119 places across 34 files. The same variable was read in up to four classes, some
with different defaults (`AIRFLOW_USERNAME` defaulted to `admin` in one file and to nothing in another),
and 23 modules called `load_dotenv()` at import. No single place listed what the service needs.

Three constraints shaped the choice:

- `src/digitaltwins` is also the published `digitaltwins` package. It must not import FastAPI or
  anything from `app/`, and its users set the same env var names.
- About 60 tests set configuration with `monkeypatch.setenv` and expect the code to see the new value
  when it runs, not when it was imported.
- `core/keycloak_verifier.py` must stay byte-identical with the builder's copy.

## Alternatives Considered

### Option A: `pydantic-settings` `BaseSettings`
- Pros: typed fields, validation and `.env` loading built in; the debt item suggested it.
- Cons: a new dependency for the published package. A cached settings object needs every
  env-setting test to clear the cache; an uncached one gives little over plain dataclasses.

### Option B: stdlib frozen dataclasses behind one `load_settings()` (chosen)
- Pros: no new dependency; one entry point; names, defaults and type coercion in one file; tests
  keep using `monkeypatch.setenv`.
- Cons: no declarative validation; coercion is a few lines written by hand.

### Option C: per-area `XSettings.from_env()` classes
- Pros: each caller reads only its own variables.
- Cons: callers must learn one entry point per area.

## Decision

Option B. `src/digitaltwins/settings.py` defines frozen dataclasses grouped by area (`postgres`,
`minio`, `airflow`, `jupyterhub`, `keycloak`, `uploads`, the `*_ENABLED` flags, ...) and one function,
`load_settings()`. It reads the environment on every call, with no cache, so values set in tests or by
the deployment are always seen. The module lives in the library so library code can use it; `app/`
imports it from there. It holds the package's only `load_dotenv()` call.

Each variable has one default. Where call sites disagreed, the deployment's value or the token verifier's
value wins, and credentials have no default.

Exceptions keep reading the environment themselves: `core/keycloak_verifier.py` (shared byte for byte
with the builder) and the inactive iRODS and Gen3 backends, which are slated for removal.
`tests/test_settings.py` fails if any other module reads `os.environ` or `os.getenv`.

## Consequences

- A new environment variable is added to `settings.py` first, then to compose and `.env.template`.
- Values that used to be read once at import (`assays.py`, `auth.py`, `chunk_store.py`) are now read
  per call. Tests set them with `monkeypatch.setenv` rather than patching module constants.
- The env var names didn't change, so no `digitaltwins` release or Airflow pin bump is needed.
- There is still no startup validation; a missing required value fails where it is used, as before.
