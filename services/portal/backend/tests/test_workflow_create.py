"""Every new workflow names its type; whether it is an SDS package is left to the build.

Run from `backend/`:
    python -m unittest tests.test_workflow_create
"""
import unittest

from tests.tool_app import bearer, make_workflow_client

BODY = {"name": "convert", "version": "1.0.0", "repository_url": "https://github.com/acme/convert",
        "source_type": "github"}


class WorkflowCreateTest(unittest.TestCase):
    GUI = ("has_backend", "frontend_folder", "frontend_build_command", "backend_folder")

    def setUp(self):
        self.client = make_workflow_client()

    def _create(self, body):
        return self.client.post("/api/workflow/create", json=body, headers=bearer("researcher"))

    def _gui(self, r):
        self.assertEqual(r.status_code, 200, r.text)
        return {k: r.json()[k] for k in self.GUI}

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

    def test_a_gui_workflow_keeps_its_frontend_layout(self):
        r = self._create({**BODY, "workflow_type": "gui", "has_backend": True, "frontend_folder": "frontend",
                          "backend_folder": "backend", "frontend_build_command": "yarn build"})
        self.assertEqual(self._gui(r), {"has_backend": True, "frontend_folder": "frontend",
                                        "frontend_build_command": "yarn build", "backend_folder": "backend"})

    def test_a_gui_workflow_defaults_to_the_plugin_build_without_a_backend(self):
        r = self._create({**BODY, "workflow_type": "gui", "frontend_folder": "ignored"})
        self.assertEqual(self._gui(r), {"has_backend": False, "frontend_folder": None,
                                        "frontend_build_command": "npm run build:plugin", "backend_folder": None})

    def test_a_gui_build_command_must_be_npm_or_yarn(self):
        r = self._create({**BODY, "workflow_type": "gui", "frontend_build_command": "make all"})
        self.assertEqual(r.status_code, 422)

    def test_a_backend_needs_both_folders(self):
        r = self._create({**BODY, "workflow_type": "gui", "has_backend": True, "frontend_folder": "frontend"})
        self.assertEqual(r.status_code, 422)

    def test_backend_folders_must_be_names_inside_code(self):
        r = self._create({**BODY, "workflow_type": "gui", "has_backend": True, "frontend_folder": "../x",
                          "backend_folder": "backend"})
        self.assertEqual(r.status_code, 422)

    def test_other_types_drop_the_gui_fields(self):
        r = self._create({**BODY, "workflow_type": "script", "has_backend": True, "frontend_folder": "f",
                          "backend_folder": "b", "frontend_build_command": "npm run x"})
        self.assertEqual(self._gui(r), {"has_backend": False, "frontend_folder": None,
                                        "frontend_build_command": None, "backend_folder": None})


if __name__ == "__main__":
    unittest.main()
