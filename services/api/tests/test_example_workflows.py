"""The workflow packages in examples/workflow/ register and deploy as they are.

The Makefile mounts examples/workflow read-only next to services/api; without it these tests skip.
"""
from pathlib import Path

import pytest

from digitaltwins.workflows.dag import find_dag_file
from digitaltwins.workflows.validation import load_workflow

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "workflow"
PACKAGES = sorted(p for p in EXAMPLES.glob("workflow_*") if p.is_dir()) if EXAMPLES.is_dir() else []


def _type(package: Path) -> str:
    return "notebook" if any((package / "code").glob("*.ipynb")) else "script"


@pytest.mark.skipif(not PACKAGES, reason="examples/workflow is not mounted")
@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_example_workflow_package_is_valid(package):
    layout = load_workflow(package, _type(package))
    assert layout.steps
    if _type(package) == "script":
        assert find_dag_file(package / "code").parent == package / "code"


BREAST_PILOT_STAND_INS = {
    "workflow_breast_inference",
    "workflow_breast_model",
    "workflow_model_finetuning",
    "workflow_statistical_analysis",
}


@pytest.mark.skipif(not PACKAGES, reason="examples/workflow is not mounted")
def test_the_breast_pilot_stand_in_workflows_are_there():
    assert BREAST_PILOT_STAND_INS <= {p.name for p in PACKAGES}


def _texts(path: Path):
    """The file's name, then its text: every cell of a spreadsheet, the whole of any other file."""
    yield path.name
    if path.suffix == ".xlsx":
        from openpyxl import load_workbook
        for sheet in load_workbook(path, read_only=True).worksheets:
            for row in sheet.iter_rows(values_only=True):
                yield from (str(v) for v in row if v is not None)
    else:
        yield path.read_text(encoding="utf-8")


@pytest.mark.skipif(not PACKAGES, reason="examples/workflow is not mounted")
@pytest.mark.parametrize("name", sorted(BREAST_PILOT_STAND_INS))
def test_a_stand_in_never_calls_itself_a_mock(name):
    """Demos show these names in Airflow, Jupyter, SEEK and the catalogue; the outputs still say
    they are placeholders."""
    package = EXAMPLES / name
    assert package.is_dir()
    hits = [f"{f.relative_to(EXAMPLES)}" for f in sorted(package.rglob("*")) if f.is_file()
            if any("mock" in t.lower() for t in _texts(f))]
    assert hits == []
