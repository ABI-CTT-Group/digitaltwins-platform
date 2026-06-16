# Importing a measurement dataset from the server terminal

A one-command way for an **admin** to import a prepared measurement dataset
straight into the portal — no GUI, no code. The dataset is uploaded to storage,
registered, pushed to FHIR, and shown in the portal as **completed** (view-only).

It accepts a dataset **folder or a `.zip`**, which **either** already contains an
annotated `fhir.json` **or** doesn't (it will auto-annotate from the files).

> **Data safety:** on success **no local copy remains** — the copy made inside
> the container is removed; the data lives only in storage (MinIO) + FHIR. Your
> original dataset on the host is never modified. (On failure the container copy
> is kept so you can retry.)

The dataset must be a SPARC measurements dataset: a `dataset_description.*` plus
`primary/<sub-XXX>/<sam-YYY>/<files>`. A `.zip` may wrap it in a single top folder
— that's unwrapped automatically. If you have an annotated `fhir.json`, put it in
the dataset root (its `uuid` / URL fields may be empty).

---

## Two steps

The dataset can live **anywhere on the host** — you just give its path.

1. **Run** the importer with the dataset (folder or `.zip`):

   | OS | Double-click | …or from a terminal |
   |---|---|---|
   | **macOS** | `scripts/import-dataset.command` (asks for the path) | `./scripts/import-dataset.sh /path/to/mydataset` |
   | **Windows** | `scripts\import-dataset.bat` (asks for the path; or drag a folder/zip onto it) | `.\scripts\import-dataset.ps1 C:\data\mydataset` |
   | **Linux** | servers are usually headless — use a terminal | `./scripts/import-dataset.sh /path/to/mydataset` |

   > **Windows:** double-click the **`.bat`** — double-clicking a `.ps1` only opens
   > an editor. If a script isn't executable on macOS/Linux, run
   > `chmod +x scripts/import-dataset.*`.

   The script copies the dataset into the `portal-backend` container — with a
   live progress bar if [`pv`](https://www.ivarch.com/programs/pv.shtml) is
   installed (`apt install pv` / `brew install pv`), otherwise it prints the
   size — then runs the in-container importer.

2. **Sign in** when prompted: open the printed link in your browser and log in
   with your normal account. You must have the **admin** role.

That's it — it validates, uploads, pushes to FHIR, prints a summary, and removes
the container-side copy.

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
import-dataset.(sh|command|ps1) <FOLDER_OR_ZIP> [--name NAME] [--password] [--username U]
```

- `FOLDER_OR_ZIP` — host path to the dataset folder or `.zip` (the script copies
  it into the container)
- `--name NAME` — dataset name (default: the folder / zip name); must be unique
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
