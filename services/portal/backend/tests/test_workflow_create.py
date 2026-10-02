"""Every new workflow names its type; whether it is an SDS package is left to the build.

Run from `backend/`:
    python -m unittest tests.test_workflow_create
"""
import unittest

from tests.tool_app import bearer, make_workflow_client

BODY = {"name": "convert", "version": "1.0.0", "repository_url": "https://github.com/acme/convert",
        "source_type": "github"}


class WorkflowCreateTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()

    def _create(self, body):
        return self.client.post("/api/workflow/create", json=body, headers=bearer("researcher"))

    def test_a_workflow_needs_a_type(self):
        self.assertEqual(self._create(BODY).status_code, 422)

    def test_a_new_workflow_is_not_known_to_be_sds_until_built(self):
        r = self._create({**BODY, "workflow_type": "gui"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["workflow_type"], r.json()["is_sds"]), ("gui", None))

    def test_the_client_cannot_set_is_sds(self):
        r = self._create({**BODY, "workflow_type": "gui", "is_sds": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["is_sds"])


if __name__ == "__main__":
    unittest.main()
