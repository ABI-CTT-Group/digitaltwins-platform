# Importing a measurement dataset from the server terminal

A one-command way for an **admin** to import a prepared measurement dataset
straight into the portal — no GUI, no code. The dataset is uploaded to storage,
registered, pushed to FHIR, and shown in the portal as **completed** (view-only).

It accepts a dataset **folder or a `.zip`**, which **either** already contains an
annotated `fhir.json` **or** doesn't (it will auto-annotate from the files).

> **Data safety:** on success **no local copy remains** — the dataset is removed
> from both the working area and the inbox; it lives only in storage (MinIO) +
> FHIR. (On failure the working copy is kept so you can retry.)

---

## Three steps

1. **Drop** your dataset into the inbox on the host — a folder **or** a `.zip`:

   ```
   clinical-dashboard/measurement-import/<your-dataset>/      (folder)
   clinical-dashboard/measurement-import/<your-dataset>.zip   (zip)
   ```

   It must be a SPARC measurements dataset: a `dataset_description.*` plus
   `primary/<sub-XXX>/<sam-YYY>/<files>`. A `.zip` may wrap the dataset in a
   single top folder — that's unwrapped automatically. If you have an annotated
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
import-dataset.(sh|command|ps1) [FOLDER_OR_ZIP] [--name NAME] [--password] [--username U]
```

- `FOLDER_OR_ZIP` — dataset folder or `.zip` (default: pick from the inbox)
- `--name NAME` — dataset name (default: the folder / zip name); must be unique
- `--password` / `--username U` — use username/password sign-in instead of the
  browser flow (only if the browser device flow isn't enabled)

(The source is always removed from the inbox after a successful import — see
"Data safety" above.)

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
