# Importing a dataset from the server terminal

This is a one-command way to import a prepared dataset into the platform, with no GUI and no code. It is meant for people with shell access to the server. It imports **measurement**, **model**, **tool** and **workflow** datasets; you always say which with `--category` (the scripts ask for it if you leave it out). The command:
- validates the dataset
- stores the files in MinIO and the metadata in the platform Postgres (tools and workflows are also registered in SEEK)
- optionally annotates the dataset and pushes it to FHIR

Afterwards the dataset appears in the portal as **completed**.

The dataset can be a **folder or a `.zip`**. A `.zip` may wrap the dataset in a single top-level folder; that folder is unwrapped automatically. What the dataset must contain depends on its category (see [Categories](#categories)). A measurement dataset is a SPARC dataset: a `dataset_description.*` file plus `primary/<sub-XXX>/<sam-YYY>/<files>`. `subjects.xlsx` and `samples.xlsx` are optional. Subjects and samples missing from them are registered from the `primary/` folder names, so every sample gets a platform UUID.

> **Data safety:** your original dataset on the host is never modified. The copy made inside the container is kept only as a local cache for the FHIR build. It is removed after a successful FHIR push, or after 7 days. The canonical data lives in MinIO, Postgres and FHIR.

---

## Two steps

The dataset can live **anywhere on the host**. You just give its path.

1. **Run** the importer with the dataset (folder or `.zip`). The scripts are in [`services/api/scripts/`](../scripts/):

   | OS | Double-click | …or from a terminal |
   |---|---|---|
   | **macOS** | `import-dataset.command` (asks for the path and category) | `services/api/scripts/import-dataset.sh /path/to/mydataset --category measurements --fhir auto` |
   | **Windows** | `import-dataset.bat` (asks for the path and category; or drag a folder or zip onto it) | `.\services\api\scripts\import-dataset.ps1 C:\data\mydataset --category measurements --fhir auto` |
   | **Linux** | servers are usually headless, so use a terminal | `services/api/scripts/import-dataset.sh /path/to/mydataset --category measurements --fhir auto` |

   > **Windows:** double-click the **`.bat`**. Double-clicking a `.ps1` only opens it in an editor. If a script isn't executable on macOS or Linux, run `chmod +x services/api/scripts/import-dataset.*`. Without `--category`, every script asks for the category before copying (and, for a tool or workflow, its type and SEEK project ID).

   The script finds the running `digitaltwins-api` container and copies the dataset into it. It shows a live progress bar if [`pv`](https://www.ivarch.com/programs/pv.shtml) is installed (`apt install pv` / `brew install pv`); otherwise it prints the size. Then it runs the importer inside the container (`python -m digitaltwins.cli.import_dataset`).

2. **Sign in** when prompted. You need the realm role **admin** or **researcher**, the same as for uploading through the portal or the REST API. On a stock deployment you are asked for your username and password. If the Keycloak device flow is enabled for the API client, you are shown a link to open in your browser instead.

---

## What it does

```
check the options → sign in (admin | researcher) → validate the dataset
→ register in Postgres + upload to MinIO (tools and workflows: register in SEEK first, as you)
→ with --fhir auto, or a measurement dataset's own fhir.json: push to FHIR (identifiers = platform UUIDs)
→ a script workflow imported by an admin: deploy its DAG to Airflow
```

The importer runs the same pipeline as `POST /datasets/uploads` in the REST API. Your sign-in is refreshed just before the commit, so a long copy does not make it expire. For large uploads from a remote machine, use the Python `UploadClient` instead (see the [README](../README.md)).

## Categories

| `--category` | Dataset layout | Required options | What the commit does |
|---|---|---|---|
| `measurements` | SPARC: `dataset_description.*` + `primary/<sub-XXX>/<sam-YYY>/<files>` | – | Postgres (dataset, subjects, samples → platform UUIDs) + MinIO |
| `models` | `dataset_description.*` + at least one file anywhere under `primary/`; no `sub-XXX/sam-YYY` folders expected | – | Postgres + MinIO; with `--fhir auto`, one FHIR `Device` |
| `tools` | exactly one `primary/tool_<name>.cwl`, the tool itself in `code/` | `--tool-type script\|notebook\|gui`, `--seek-project-id P` | registered in SEEK project `P` as you, then Postgres + MinIO; with `--fhir auto`, one `ActivityDefinition` |
| `workflows` | one `primary/workflow_<name>.cwl` whose steps run `tool_<name>.cwl` files also in `primary/` | `--workflow-type script\|notebook\|gui`, `--seek-project-id P` | the workflow and each of its tools registered in SEEK, then Postgres + MinIO; a script workflow imported by an **admin** has its DAG deployed to Airflow (a researcher's waits for an admin: `POST /workflows/{uuid}/deploy`) |

For tools and workflows, the SEEK title is the dataset name: `--name`, or the folder or zip name by default.

```
services/api/scripts/import-dataset.sh /path/to/my_measurements --category measurements --fhir auto
services/api/scripts/import-dataset.sh /path/to/model_skin_test --category models --fhir auto
services/api/scripts/import-dataset.sh /path/to/tool_convert --category tools --tool-type script --seek-project-id 1
services/api/scripts/import-dataset.sh /path/to/wf_convert --category workflows --workflow-type script --seek-project-id 1
```

### A measurement dataset's own annotation (`fhir.json`)

If a measurement dataset has a `fhir.json` at its root, it is used as the dataset's FHIR annotation instead of the automatic one, and pushed to FHIR whatever `--fhir` says. It uses the same format as the portal's annotation (`{"dataset": {...}, "patients": [...]}`). Refer to subjects and samples by folder name; the platform assigns the UUIDs. It is checked against the dataset first: every patient, `samplePath` and series must name a folder under `primary/`, or the import stops with exit code 2. The `fhir.json` itself is not stored as a data file.

### Subjects without samples

A `primary/<subject>` folder with no sample folders can't be registered. The importer prints a `!` warning for each one and imports the rest.

## Options

```
import-dataset.(sh|command|ps1) <FOLDER_OR_ZIP> --category measurements|models|tools|workflows
    [--name NAME] [--description TEXT] [--fhir auto|none]
    [--tool-type script|notebook|gui] [--workflow-type script|notebook|gui] [--seek-project-id P]
    [--password] [--username U]
```

- `FOLDER_OR_ZIP`: host path to the dataset folder or `.zip`. The script copies it into the container.
- `--category`: the dataset category; required (the scripts ask for it if it's missing). Any other value is rejected.
- `--name NAME`: dataset name. The default is the folder or zip name. Names don't have to be unique, because datasets are identified by UUID.
- `--description TEXT`: dataset description (a model's `Device` description).
- `--fhir auto`: annotate the dataset automatically and push the result to FHIR. The default, `none`, stores the dataset only; you can annotate and push it later from the portal or with `POST /datasets/{uuid}/fhir/push`. (The legacy portal importer always pushed to FHIR.)
- `--tool-type`, `--workflow-type`, `--seek-project-id`: required for tools and workflows (see [Categories](#categories)).
- `--password` / `--username U`: sign in with a username and password without trying the device flow first.

## Exit codes

- `0`: success
- `1`: the commit or the FHIR push failed.
  - If the commit failed, the dataset stays staged; retry it with `POST /datasets/uploads/{upload_id}/approve` (the importer prints the exact call).
  - If only the FHIR push failed, the dataset is stored; retry with `POST /datasets/{uuid}/fhir/push`.
- `2`: invalid dataset or options: the dataset doesn't match its category, a broken or too large zip (limit: `MAX_UPLOAD_MB`, 20 GiB by default), a `fhir.json` that doesn't match the dataset, a missing or unknown `--category`, a missing path, or missing tool/workflow options
- `3`: not authorised or sign-in failed: the account has neither the `admin` nor the `researcher` role, Keycloak could not be reached, or the sign-in expired before the commit (the dataset stays staged; retry it with `POST /datasets/uploads/{upload_id}/approve`)

## Prerequisites (one-time, ops)

- Operators have the `admin` or `researcher` realm role. Tool and workflow importers must also be members of the SEEK project they import into.
- The stack is up (`docker compose up -d`). The importer runs inside the `digitaltwins-api` container.
- Optional: enable the **device flow** on the Keycloak client used by the API (`KEYCLOAK_CLIENT_ID`) to sign in through the browser instead of typing a password. It is off in the stock realm.
