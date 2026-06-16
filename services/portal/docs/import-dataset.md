# Importing a measurement dataset from the server terminal

A one-command way for an **admin** to import a prepared measurement dataset
straight into the portal — no GUI, no code. The dataset is uploaded to storage,
registered, pushed to FHIR, and shown in the portal as **completed** (view-only).

It accepts a dataset folder that **either** already contains an annotated
`fhir.json` **or** doesn't (it will auto-annotate from the files).

---

## Three steps

1. **Drop** your dataset folder into the inbox on the host:

   ```
   clinical-dashboard/measurement-import/<your-dataset>/
   ```

   The folder must be a SPARC measurements dataset: a `dataset_description.*`
   plus `primary/<sub-XXX>/<sam-YYY>/<files>`. If you have an annotated
   `fhir.json`, put it in the dataset root (its `uuid` / URL fields may be empty).

2. **Run** the importer:

   - **macOS:** double-click `scripts/import-dataset.command`
   - **Windows:** right-click `scripts/import-dataset.ps1` → *Run with PowerShell*
   - **Linux / any terminal:** `./scripts/import-dataset.sh`

   (You can pass the folder name to skip the picker, e.g. `./scripts/import-dataset.sh my-dataset`.)

3. **Sign in** when prompted: open the printed link in your browser and log in
   with your normal account. You must have the **admin** role.

That's it — it validates, uploads, pushes to FHIR, and prints a summary. The
local copy is removed afterward (the data lives in storage).

---

## What it does

```
sign in (admin) → validate dataset
   ├─ has fhir.json → check it matches this dataset → import
   └─ no fhir.json  → auto-annotate from the files   → import
→ upload to MinIO → push to FHIR (hapi) → mark completed → clean up local copy
```

- **With `fhir.json`:** it's cross-checked against the dataset (patients,
  per-type sample counts, imaging series names). A mismatched / unrelated
  `fhir.json` is rejected.
- **Placeholder ids:** `uuid` and URL fields are (re)generated from the folder
  names; the real platform ids will replace them later via digitaltwins-api.
- **View-only:** imported datasets appear in the portal for viewing / preview /
  export. They are not re-annotated or re-approved through the GUI.

## Options

```
import-dataset.(sh|command|ps1) [FOLDER] [--name NAME] [--consume] [--password] [--username U]
```

- `FOLDER` — dataset folder (default: pick from the inbox)
- `--name NAME` — dataset name (default: the folder name); must be unique
- `--consume` — delete the source folder from the inbox after a successful import
- `--password` / `--username U` — use username/password sign-in instead of the
  browser flow (only if the browser device flow isn't enabled)

## Exit codes

- `0` success
- `1` user error — not signed in as admin, invalid dataset, mismatched
  `fhir.json`, or duplicate name
- `2` pipeline failure (upload / FHIR push) — the local copy is kept so you can
  fix the issue and re-run

## Prerequisites (one-time, ops)

- The portal Keycloak client has the **device flow** enabled (or use `--password`).
- The admin role is assigned to the operators who will run this.
- The stack is up (`docker compose up -d`); the importer runs inside
  `portal-backend`.
