"""Registration errors and steps reach the builder's log.

Run from `services/builder/`:
    python -m pytest tests/test_registration_logging.py
"""
import json
import logging
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from tests.tool_app import bearer, make_client, make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.router import workflow_router, workflow_tool_plugin
from app.utils.request_logging import install_request_error_logging

TOOL = {"name": "Convert", "version": "1.0.0", "repository_url": "https://github.com/acme/convert",
        "frontend_folder": "", "frontend_build_command": "", "label": "Script", "has_backend": False,
        "backend_folder": None, "backend_deploy_command": ""}
WORKFLOW = {"name": "Pipeline", "version": "1.0.0", "repository_url": "https://github.com/acme/pipeline",
            "workflow_type": "script"}


class RequestErrorLoggingTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        install_request_error_logging(app)

        @app.get("/missing")
        def missing():
            raise HTTPException(status_code=404, detail="Plugin not found")

        @app.get("/broken")
        def broken():
            raise HTTPException(status_code=502, detail="SEEK is down")

        @app.get("/typed")
        def typed(n: int):
            return n

        self.client = TestClient(app)

    def test_a_client_error_is_a_warning_with_its_reason_and_no_query_string(self):
        with self.assertLogs("app.request", "WARNING") as logs:
            r = self.client.get("/missing?token=abc")

        self.assertEqual((r.status_code, r.json()), (404, {"detail": "Plugin not found"}))
        [record] = logs.records
        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.getMessage(), "GET /missing -> 404: Plugin not found")

    def test_a_server_error_is_an_error(self):
        with self.assertLogs("app.request", "WARNING") as logs:
            r = self.client.get("/broken")

        self.assertEqual((r.status_code, r.json()), (502, {"detail": "SEEK is down"}))
        self.assertEqual(logs.records[0].levelno, logging.ERROR)
        self.assertEqual(logs.records[0].getMessage(), "GET /broken -> 502: SEEK is down")

    def test_a_validation_error_is_logged_and_its_response_is_unchanged(self):
        plain = FastAPI()

        @plain.get("/typed")
        def typed(n: int):
            return n

        with self.assertLogs("app.request", "WARNING") as logs:
            r = self.client.get("/typed?n=x")

        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json(), TestClient(plain).get("/typed?n=x").json())
        self.assertTrue(logs.records[0].getMessage().startswith("GET /typed -> 422: "))


class ToolRegistrationStepsTest(unittest.TestCase):
    def setUp(self):
        self.client = make_client()

    def _create(self):
        return self.client.post("/api/builder/tools/create", json=TOOL, headers=bearer("researcher")).json()["id"]

    def test_create_is_logged_with_the_user(self):
        with self.assertLogs(workflow_tool_plugin.logger.name, "INFO") as logs:
            plugin_id = self._create()

        self.assertIn(f"Registration tools create: plugin_id={plugin_id} name=Convert user=researcher",
                      [r.getMessage() for r in logs.records])

    def test_annotation_is_logged_with_the_user(self):
        plugin_id = self._create()

        with self.assertLogs(workflow_tool_plugin.logger.name, "INFO") as logs:
            r = self.client.post(f"/api/builder/tools/plugin/{plugin_id}/annotation",
                                 json={"fhir_note": "{}", "sparc_note": ""}, headers=bearer("researcher"))

        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn(f"Registration tools annotate: plugin_id={plugin_id} user=researcher",
                      [r.getMessage() for r in logs.records])

    def test_build_request_is_logged_with_the_user(self):
        plugin_id = self._create()
        original = workflow_tool_plugin.execute_build_in_background
        workflow_tool_plugin.execute_build_in_background = lambda **kwargs: None
        self.addCleanup(setattr, workflow_tool_plugin, "execute_build_in_background", original)

        with self.assertLogs(workflow_tool_plugin.logger.name, "INFO") as logs:
            r = self.client.post(f"/api/builder/tools/plugin/{plugin_id}/build", json={}, headers=bearer("researcher"))

        build_id = r.json()["build_id"]
        self.assertIn(f"Registration tools build requested: plugin_id={plugin_id} build_id={build_id} user=researcher",
                      [r.getMessage() for r in logs.records])


class WorkflowRegistrationStepsTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()

    def _create(self):
        r = self.client.post("/api/builder/workflow/create", json=WORKFLOW, headers=bearer("researcher"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_create_is_logged_with_the_user(self):
        with self.assertLogs(workflow_router.logger.name, "INFO") as logs:
            workflow_id = self._create()

        self.assertIn(f"Registration workflows create: workflow_id={workflow_id} name=Pipeline user=researcher",
                      [r.getMessage() for r in logs.records])

    def test_annotation_is_logged_with_the_user(self):
        workflow_id = self._create()

        with self.assertLogs(workflow_router.logger.name, "INFO") as logs:
            r = self.client.post(f"/api/builder/workflow/{workflow_id}/annotation",
                                 json={"fhir_note": json.dumps({"steps": []}), "sparc_note": ""},
                                 headers=bearer("researcher"))

        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn(f"Registration workflows annotate: workflow_id={workflow_id} user=researcher",
                      [r.getMessage() for r in logs.records])

    def test_build_request_is_logged_with_the_user(self):
        workflow_id = self._create()
        original = workflow_router.execute_build_in_background
        workflow_router.execute_build_in_background = lambda **kwargs: None
        self.addCleanup(setattr, workflow_router, "execute_build_in_background", original)

        with self.assertLogs(workflow_router.logger.name, "INFO") as logs:
            r = self.client.post(f"/api/builder/workflow/{workflow_id}/build", json={}, headers=bearer("researcher"))

        self.assertEqual(r.status_code, 200, r.text)
        build_id = r.json()["build_id"]
        self.assertIn(f"Registration workflows build requested: workflow_id={workflow_id} build_id={build_id} "
                      f"user=researcher", [r.getMessage() for r in logs.records])


if __name__ == "__main__":
    unittest.main()
