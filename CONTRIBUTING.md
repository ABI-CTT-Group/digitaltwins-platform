# Contributing to the DigitalTWINS platform

Thanks for helping improve the platform. This page covers how changes get from an
idea into `main`.

By taking part you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Reporting issues

Use the [issues page](https://github.com/ABI-CTT-Group/digitaltwins-platform/issues)
and pick a template: bug report, feature request or documentation request. Check
existing issues first. Never paste passwords, tokens or the contents of `.env` /
`secrets.env`; replace them with `<REDACTED>`.

## Making a change

1. **Branch.** Fork the repository, or create a branch if you have write access.
   Name it after the change, e.g. `feat/airflow-worker-gpu-opt-in` or
   `fix/portal-restore-sqlite-registry`.
2. **Commit.** Use [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `build:`, `chore:`,
   with an optional scope, e.g. `fix(airflow): ...`. Keep each commit to one logical
   change so it can be reverted on its own.
3. **Test.** Run the unit tests and the linters before you push:
   ```bash
   make test   # all five unit-test suites, in pinned containers
   make lint   # ruff, eslint and vue-tsc (report-only in CI)
   ```
   You need only Docker and GNU make. See [docs/testing.md](docs/testing.md) for
   running one suite, the integration tests, and the safety rules (never run the
   builder tests inside the live `builder` container).
4. **Document.** Update the README, `docs/` or the service's README when behaviour
   changes. If the change makes a significant design decision (a real choice between
   alternatives, or a deviation from an existing convention), add an Architecture
   Decision Record in [docs/decisions/](docs/decisions/) using its
   [template](docs/decisions/TEMPLATE.md).
5. **Open a pull request** against `main` and fill in the template. CI runs the
   test suites that your change affects, plus gitleaks on the PR's commits. These
   checks must pass before merging: `api unit tests`, `builder unit tests`,
   `frontend unit tests`, `jupyterhub unit tests` and `gitleaks (PR commits)`.

## Keeping secrets out of git

A [gitleaks](https://github.com/gitleaks/gitleaks) pre-commit hook blocks commits
that contain secrets. Install it once per clone:

```bash
pip install pre-commit
pre-commit install
```

Use placeholders such as `<REDACTED>` for passwords, keys and tokens in code, docs
and examples. Don't bypass the hook. Real values belong only in your local
`secrets.env`, which is git-ignored.

## Working on a running deployment

To get a change into a running platform, and to see what each kind of change
(Keycloak, secrets, env vars, DAGs, images) additionally needs, see
[docs/development.md](docs/development.md). After changing a service, rebuild and
restart its containers, e.g. `docker compose build api && docker compose up -d api`.

## AI coding agents

Agents working in this repository follow [AGENTS.md](AGENTS.md): planning and
summary documents go to timestamped folders in `docs/artifacts/`, and ADRs go in the
same pull request as the code they describe.

`AGENTS.md` is the single source of agent instructions. `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md` and `.agents/rules/main.md` only point to it, and
`make docs-check` fails if one of them holds anything else. Edit `AGENTS.md`, or a
service's own `AGENTS.md`, to change what agents are told.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
