"""SEEK tool tags → the dashboard's workflow type.

Run from `backend/`:
    python -m unittest tests.test_workflow_type
"""
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.utils import get_workflow_type  # noqa: E402


class WorkflowTypeTest(unittest.TestCase):
    def test_each_tool_type_is_recognised(self):
        for tag in ("script", "gui", "notebook"):
            with self.subTest(tag=tag):
                self.assertEqual(get_workflow_type(["tool", tag.upper()]), tag)

    def test_conflicting_types_are_an_error(self):
        self.assertEqual(get_workflow_type(["tool", "script", "notebook"]), "error")

    def test_no_type_is_other(self):
        self.assertEqual(get_workflow_type(["workflow"]), "other")


if __name__ == "__main__":
    unittest.main()
