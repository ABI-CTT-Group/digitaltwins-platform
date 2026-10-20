"""Import a measurement, model, tool or workflow dataset from inside the api container.

    python -m digitaltwins.cli.import_dataset <folder|zip> --category measurements [--name N] [--fhir auto] [--move]
    python -m digitaltwins.cli.import_dataset <folder|zip> --category tools \
        --tool-type script|notebook|gui --seek-project-id P [--fhir auto]
    python -m digitaltwins.cli.import_dataset <folder|zip> --category workflows \
        --workflow-type script|notebook|gui --seek-project-id P [--fhir auto]
    python -m digitaltwins.cli.import_dataset <folder|zip> --category models [--fhir auto]

Signs in with Keycloak (browser device flow, or ``--password``), checks the
upload role, then runs the same pipeline as ``/datasets/uploads`` in-process:
validation (SPARC, a model's SDS files, a tool's ``primary/tool_*.cwl``, or a workflow's layout;
a measurement dataset's root ``fhir.json``, if any, becomes its FHIR annotation) →
commit (Postgres + MinIO; tools and workflows are also registered in SEEK as
the signed-in user, a workflow's tools as tool datasets) → optional FHIR push (a
model's is one Device) → for a script workflow imported by an admin, its DAG is
deployed to Airflow (a researcher's waits for an admin; a failed deploy is
reported but does not fail the import). The access token is refreshed just before
the commit, so a long copy does not outlive it. The
``scripts/import-dataset.*`` wrappers copy a dataset from the host into the
container and call this.

Exit codes: 0 ok, 1 commit / FHIR failed, 2 invalid dataset or options, 3 not authorised.
A failed commit leaves the dataset staged; retry it with ``POST /datasets/uploads/{id}/approve``.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from .. import models, tools, workflows
from ..core.connection import Connection
from ..measurements import jobs, pipeline, sessions
from ..measurements.staging import dataset_dir, max_upload_bytes, staging_root
from ..measurements.validation import (
    extract_uploaded_archive, resolve_project_root, sampleless_subjects, validate_sparc_structure,
)
from ..models.validation import validate_model_structure
from ..tools.validation import find_tool_cwl
from ..workflows.validation import load_workflow
from .keycloak_login import is_admin, login, refresh

MEASUREMENTS = "measurements"


def _parse(argv):
    parser = argparse.ArgumentParser(prog="python -m digitaltwins.cli.import_dataset", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="dataset folder or .zip")
    parser.add_argument("--name", help="dataset name (default: folder / zip name)")
    parser.add_argument("--description")
    parser.add_argument("--fhir", choices=["none", "auto"], default="none", help="auto-annotate and push FHIR")
    parser.add_argument("--category", help="required: measurements, models, tools or workflows")
    parser.add_argument("--tool-type", choices=["script", "notebook", "gui"], help="tools only (required)")
    parser.add_argument("--seek-project-id", type=int,
                        help="tools and workflows only (required): SEEK project to register in")
    parser.add_argument("--workflow-type", choices=["script", "notebook", "gui"], help="workflows only (required)")
    parser.add_argument("--move", action="store_true", help="move (not copy) the folder into staging")
    parser.add_argument("--password", action="store_true", help="password login instead of the device flow")
    parser.add_argument("--username")
    return parser.parse_args(argv)


def _fail(code: int, message: str) -> int:
    print(f"  ✗ {message}", file=sys.stderr)
    return code


def _retry_hint(upload_id: str) -> str:
    return f"the dataset stays staged; retry with POST /datasets/uploads/{upload_id}/approve"


def _read_annotation(root: Path) -> dict:
    """A measurement dataset's own ``fhir.json``, checked against its ``primary/`` folders."""
    descriptions = json.loads((root / "fhir.json").read_text(encoding="utf-8"))
    if not isinstance(descriptions, dict):
        raise ValueError("not a JSON object")
    pipeline.check_descriptions_match(descriptions, root)
    return descriptions


def _report_dag(conn, dataset_uuid: str) -> None:
    """Say whether the imported script workflow's DAG is in Airflow."""
    with conn.cursor() as cur:
        cur.execute("SELECT seek_id, dag_status, dag_error FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))
        seek_id, status, error = cur.fetchone()
    conn.commit()
    if status == "deployed":
        print(f"  ✓ DAG deployed as workflow_{seek_id}")
    elif status == "failed":
        print(f"  ✗ DAG deploy failed: {error}", file=sys.stderr)
    else:
        print(f"  DAG not deployed yet: an admin deploys it with POST /workflows/{dataset_uuid}/deploy")


def main(argv=None) -> int:
    args = _parse(argv)
    path = Path(args.path)
    if not path.exists():
        return _fail(2, f"No such path: {path}")
    supported = {MEASUREMENTS, models.CATEGORY, tools.CATEGORY, workflows.CATEGORY}
    if args.category not in supported:
        problem = "Missing --category" if args.category is None else f"Unknown category {args.category!r}"
        return _fail(2, f"{problem}; use one of: {', '.join(sorted(supported))}")
    tool = args.category == tools.CATEGORY
    if tool and (args.tool_type is None or args.seek_project_id is None):
        return _fail(2, "Tool imports need --tool-type and --seek-project-id")
    workflow = args.category == workflows.CATEGORY
    if workflow and (args.workflow_type is None or args.seek_project_id is None):
        return _fail(2, "Workflow imports need --workflow-type and --seek-project-id")
    measurement = not (tool or workflow or args.category == models.CATEGORY)

    try:
        username, token, refresh_token = login(use_password=args.password, username=args.username)
    except PermissionError as e:
        return _fail(3, str(e))
    except Exception as e:  # Keycloak unreachable, sign-in timed out, …
        return _fail(3, f"Login failed: {e}")

    extracted = None
    try:
        if path.is_file():
            try:
                extracted = extract_uploaded_archive(staging_root() / "import", path,
                                                     max_total_bytes=max_upload_bytes())
            except Exception as e:
                return _fail(2, f"Cannot extract {path.name}: {e}")
            source = extracted
        else:
            source = path
        if tool:
            try:
                find_tool_cwl(source)
            except ValueError as e:
                return _fail(2, str(e))
        elif workflow:
            try:
                load_workflow(source, args.workflow_type)
            except ValueError as e:
                return _fail(2, str(e))
        else:
            validate = validate_model_structure if args.category == models.CATEGORY else validate_sparc_structure
            ok, message = validate(source)
            if not ok:
                return _fail(2, message)
        root = resolve_project_root(source)
        descriptions = None
        if measurement:
            for warning in sampleless_subjects(root):
                print(f"  ! {warning}")
            if (root / "fhir.json").is_file():
                try:
                    descriptions = _read_annotation(root)
                except ValueError as e:
                    return _fail(2, f"Invalid fhir.json: {e}")
                print("  Using the dataset's fhir.json as its FHIR annotation")

        conn, _ = Connection().connect()
        try:
            upload_id = sessions.create_session(
                conn, category=args.category, name=args.name or (path.stem if path.is_file() else path.name),
                description=args.description, source_kind="zip" if path.is_file() else "folder",
                commit_mode="on_finalize", fhir_mode="descriptions" if descriptions else args.fhir,
                fhir_descriptions=descriptions,
                tool_type=args.tool_type if tool else None,
                seek_project_id=args.seek_project_id if tool or workflow else None,
                workflow_type=args.workflow_type if workflow else None,
            )
            target = dataset_dir(upload_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            print(f"  Importing as {username}…")
            if extracted is not None or args.move:
                shutil.move(str(root), str(target))
            else:
                shutil.copytree(root, target)
            if args.move and path.is_file():
                path.unlink()  # the staged zip; its contents now live in the dataset dir
            if descriptions:
                (target / "fhir.json").unlink()  # the annotation, not data to publish
            if refresh_token:
                try:
                    token = refresh(refresh_token)
                except Exception as e:
                    sessions.update_session(conn, upload_id, status="failed", failure_stage="auth",
                                            failure_message=str(e))
                    return _fail(3, f"{e} {_retry_hint(upload_id)}")
            sessions.update_session(conn, upload_id, status="processing")
            script_workflow = workflow and args.workflow_type == "script"
            jobs.run_commit_and_push(upload_id, token, deploy_dag=script_workflow and is_admin(token))

            session = sessions.get_session(conn, upload_id)
            if session["status"] != "completed":
                return _fail(1, f"Commit failed: {session['failure_message']}; {_retry_hint(upload_id)}")
            dataset = pipeline.get_dataset_row(conn, session["dataset_uuid"])
            if script_workflow:
                _report_dag(conn, session["dataset_uuid"])
        finally:
            conn.close()
    finally:
        if extracted is not None:
            shutil.rmtree(extracted, ignore_errors=True)

    print(f"  ✓ Imported dataset {session['dataset_uuid']} (FHIR: {dataset['fhir_status']})")
    if dataset["fhir_status"] == "failed":
        return _fail(1, f"FHIR push failed; retry with POST /datasets/{session['dataset_uuid']}/fhir/push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
