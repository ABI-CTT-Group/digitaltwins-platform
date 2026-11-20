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


@pytest.mark.skipif(not PACKAGES, reason="examples/workflow is not mounted")
def test_the_mock_workflows_are_there():
    names = {p.name for p in PACKAGES}
    assert {
        "workflow_mock_inference",
        "workflow_mock_breast_model",
        "workflow_mock_model_finetuning",
        "workflow_mock_statistical_analysis",
    } <= names
