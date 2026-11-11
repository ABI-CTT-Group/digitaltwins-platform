# Tasks: JupyterHub service token secret

- [x] Plan; sync to docs/artifacts/
- [x] Draft ADR docs/decisions/2026-10-16-jupyterhub-service-token-secret.md
- [x] Await plan approval
- [x] Hub config test (red) -> revoke block + os.environ (green)
- [x] API token tests (red) -> drop defaults in hub.py / assays.py (green)
- [x] Templates + compose :? ; gen-env and compose-config checks
- [x] Docs: production.md, INSTALL-BUNDLE.md; demo gen-new-secrets.sh (local)
- [x] Local rotation + regression checks; rebuild/restart jupyterhub, digitaltwins-api
- [x] Walkthrough; sync artifacts; gitleaks; ADR -> Accepted
