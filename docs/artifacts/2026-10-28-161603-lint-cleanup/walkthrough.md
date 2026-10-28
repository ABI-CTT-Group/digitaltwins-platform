# Walkthrough: make `make lint` pass

Goal: `make lint` (ruff, eslint and vue-tsc) exits 0 with no behaviour change. Plan:
[implementation-plan.md](implementation-plan.md). These findings were all on `main` before this change,
and CI runs lint report-only.

| Check | Before | After |
|---|---|---|
| ruff (`E4,E7,E9,F`, api + builder + jupyterhub) | 135 errors | 0 |
| eslint (portal frontend) | 11 errors, 22 warnings | 0 |
| vue-tsc (portal frontend) | 14 errors | 0 |

## What changed

| Step | Change |
|---|---|
| 1 | ruff's safe automatic fixes (57): unused imports, unused `as e`, f-strings with no placeholders. |
| 2 | builder: the second `get_plugin_builds` (`GET /plugin/build/{build_id}/deploys`) is now `get_build_deploys`. Both routes already worked; only the module name was shadowed. Its default OpenAPI operationId changes. |
| 3 | api, E402: imports moved above `load_dotenv()` / `urllib3.disable_warnings()` (no module reads env vars at import time); the `Request.form` patch in `app/main.py` moved below the imports; redundant `sys.path` guards dropped from 3 tests (`pyproject.toml` sets `pythonpath`); the notebook import moved to the top of its cell. The circular import at the bottom of `gen3/querier.py` stays, with `# noqa: E402` and the reason. |
| 4 | api + builder: dead locals removed (the `json.loads` that validates `config.portal.json` is kept); bare `except:` → `except Exception:`; lambdas → nested `def`s; `l` → `link`; one-line `if` split; `__all__` added to `digitaltwins/__init__.py`; the `tool_bucket` fixture moved to `tests/conftest.py`, with its 5 imports and 2 `noqa: F811` removed and `services/api/AGENTS.md` updated. |
| 5 | portal eslint: `:key` (the CWL input/output name) on 6 `v-for`s; 4 extra semicolons in `bootstrap/index.ts` (the `window.Vue`/`Pinia`/... globals stay); an unused slot prop; unused imports and bindings; `argsIgnorePattern: '^_'` and `ignoreRestSiblings` in `.eslintrc.js`. |
| 6 | portal vue-tsc: `RegistryView` refs cast to `Ref<T[]>` (this also clears 6 errors in the `*OverallView` pages); `.find` used as a loop → `?.forEach`; typed `defineModel<boolean>`; the `jszip` type; `?? ''` for a nullable status; `ToolInformationStep` in `UploadToolForm`; `as PluginOption` on `glslify(...)`. |
| 7 | 5 leftovers added to `docs/future_refactoring.md` ("Lint cleanup leftovers"). |
| 8 | CI: the `lint (report-only)` job is now `lint`, without `continue-on-error`; the frontend step runs even when the Python step fails. Docs no longer call lint report-only. ADR [2026-10-28-lint-required-check.md](../../decisions/2026-10-28-lint-required-check.md). `lint` is added to the "CI required checks" ruleset after merge. |

## Decisions made during implementation

- vue-tsc had been hiding a second error in `vite.config.ts`: the `test` key. vitest 3.2.7 adds that key
  to its own nested vite 7.3.6, while the file imports vite 6.4.1. Aligning the versions changes the
  lockfile, so the key got a `@ts-expect-error` with the reason; that becomes an error itself once the
  versions match. Both vite workarounds are listed in `docs/future_refactoring.md`.
- `metadata_convertor.py` keeps `except Exception:` rather than narrower exceptions, to keep its
  behaviour; narrowing is listed as follow-up work.

## Verification

- `make lint`: exit 0.
- `make test-api`: 391 passed, 1 skipped (as before). With `-m integration --setup-plan`, all 61 tests
  that use `tool_bucket` resolve it from `conftest.py`.
- `make test-builder`: 221 passed, 11 skipped (as before).
- `make test-frontend`: 33 files, 162 tests passed.
- `vite build` (offline, same Node image) succeeds with the new `vite.config.ts`.
- Edits were applied as exact-text replacements that fail unless each match is unique.

## Docker

The api, builder and portal-frontend images contain this code. No containers run on the machine where
this was done, so nothing was rebuilt. On a deployment, rebuild only those services:

```
docker compose build api builder portal-frontend
docker compose up -d --no-deps api builder portal-frontend
```
