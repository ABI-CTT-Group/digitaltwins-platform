"""Static checks and folder layout for deploying a script workflow's Airflow DAG.

A deployed DAG lives in ``<dags dir>/workflow_<seek_id>/`` and names itself
after that folder (``dag_id=Path(__file__).parent.name``), so its author never
needs to know the SEEK id, which only exists once the workflow is registered.
``run_assay`` triggers ``workflow_<seek_id>``. Nothing here executes the
author's code. See docs/decisions/2026-10-13-deploy-script-workflow-dags.md.
"""
import ast
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DAG_ID_EXPR = "Path(__file__).parent.name"
_ACCEPTED = {DAG_ID_EXPR, f"pathlib.{DAG_ID_EXPR}"}
_HOW = ("Name the DAG after its folder:\n"
        "    DAG_ID = Path(__file__).parent.name\n"
        "    @dag(dag_id=DAG_ID, ...)")
_DAG_NAMES = {"dag", "DAG"}


def dags_dir() -> Optional[Path]:
    """The Airflow dags folder as mounted in this container, or None when deploying is not set up."""
    value = os.getenv("AIRFLOW_DAGS_DIR")
    return Path(value) if value else None


def dag_id_for(seek_id) -> str:
    """``workflow_<seek_id>``, the DAG id ``run_assay`` triggers. Rejects anything but digits."""
    if seek_id is None or not re.fullmatch(r"[0-9]+", str(seek_id)):
        raise ValueError(f"Not a SEEK workflow id: {seek_id!r}")
    return f"workflow_{seek_id}"


def _named_dag(func: ast.expr) -> bool:
    return (isinstance(func, ast.Name) and func.id in _DAG_NAMES) or \
        (isinstance(func, ast.Attribute) and func.attr in _DAG_NAMES)


def _dag_definitions(tree: ast.Module) -> List[Optional[ast.expr]]:
    """The dag_id argument of each DAG the module defines (None when it has none)."""
    found: List[Optional[ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _named_dag(node.func):
            dag_id = next((k.value for k in node.keywords if k.arg == "dag_id"), None)
            found.append(dag_id if dag_id is not None else (node.args[0] if node.args else None))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.extend(None for d in node.decorator_list if _named_dag(d))  # bare ``@dag``
    return found


def _module_names(tree: ast.Module) -> Dict[str, ast.expr]:
    names: Dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            names[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            names[node.target.id] = node.value
    return names


def _check_dag_id(rel: str, dag_id: Optional[ast.expr], tree: ast.Module) -> None:
    if dag_id is None:
        raise ValueError(f"{rel}: the DAG has no dag_id. {_HOW}")
    got = ast.unparse(dag_id)
    if got in _ACCEPTED:
        return
    if isinstance(dag_id, ast.Name):
        value = _module_names(tree).get(dag_id.id)
        if value is not None and ast.unparse(value) in _ACCEPTED:
            return
        if value is not None:
            got = f"{dag_id.id} = {ast.unparse(value)}"
    raise ValueError(f"{rel}: dag_id must be {DAG_ID_EXPR}, got {got}. {_HOW}")


def find_dag_file(code: Path) -> Path:
    """The single DAG file directly in ``code/``, after checking its dag_id is folder-derived.

    Only files Airflow would import are considered: ``*.py`` mentioning both
    "airflow" and "dag" (its safe-mode rule). Raises ValueError with a message
    meant for the workflow's author.
    """
    definitions: List[Tuple[Path, Optional[ast.expr], ast.Module]] = []
    for path in sorted(code.rglob("*.py")) if code.is_dir() else []:
        raw = path.read_bytes().lower()
        if b"airflow" not in raw or b"dag" not in raw:
            continue
        rel = str(path.relative_to(code.parent))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise ValueError(f"{rel}: cannot be parsed: {exc}") from exc
        definitions.extend((path, dag_id, tree) for dag_id in _dag_definitions(tree))

    if not definitions:
        raise ValueError(f"No Airflow DAG found in code/. A script workflow needs exactly one DAG file there. {_HOW}")
    if len(definitions) > 1:
        files = ", ".join(sorted({str(p.relative_to(code.parent)) for p, _, _ in definitions}))
        raise ValueError(f"A script workflow needs exactly one DAG; found {len(definitions)} in {files}.")
    path, dag_id, tree = definitions[0]
    rel = str(path.relative_to(code.parent))
    if path.parent != code:
        raise ValueError(f"{rel}: the DAG file must be directly in code/, next to the tools it imports.")
    _check_dag_id(rel, dag_id, tree)
    return path


def _chown_like(root: Path, owner: Path) -> None:
    """Give ``root`` and everything in it ``owner``'s uid/gid, so the host user can still manage the dags folder."""
    if os.geteuid() != 0:
        return
    st = owner.stat()
    os.chown(root, st.st_uid, st.st_gid)
    for path in root.rglob("*"):
        os.chown(path, st.st_uid, st.st_gid, follow_symlinks=False)


def write_dag_folder(code: Path, dags: Path, dag_id: str, dag_file: str) -> Path:
    """Copy ``code/`` to ``dags/<dag_id>/`` so Airflow never sees a half-written folder.

    The copy is staged next to the target with an ``.airflowignore`` hiding
    everything, renamed into place (replacing a previous deploy), then given an
    ``.airflowignore`` that shows Airflow only ``dag_file``: tool modules are
    imported by the DAG's tasks, never parsed as DAGs. Any ``.airflowignore``
    shipped in ``code/`` is replaced.
    """
    target = dags / dag_id
    staging = dags / f".deploy-{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        (staging / ".airflowignore").write_text("*\n")
        shutil.copytree(code, staging, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".airflowignore"))
        _chown_like(staging, dags)
        if target.exists():
            shutil.rmtree(target)
        os.rename(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    pending = target / ".airflowignore.tmp"
    pending.write_text(f"*.py\n!/{dag_file}\n")
    _chown_like(pending, dags)
    os.replace(pending, target / ".airflowignore")
    return target


def remove_dag_folder(dags: Path, seek_id) -> None:
    """Remove ``dags/workflow_<seek_id>/``; a missing folder is fine."""
    target = dags / dag_id_for(seek_id)
    if target.exists():
        shutil.rmtree(target)
