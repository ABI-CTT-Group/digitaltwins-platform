"""Keycloak on /api/workflow: any valid token reads, admin|researcher write (as /api/tools).

Run from `backend/`:
    python -m unittest tests.test_workflow_auth
"""
import unittest

from tests.tool_app import bearer, make_workflow_client


class WorkflowAuthTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()

    def test_no_token_is_401(self):
        self.assertEqual(self.client.get("/api/workflow/").status_code, 401)
        self.assertEqual(self.client.get("/api/workflow/metadata").status_code, 401)
        self.assertEqual(self.client.post("/api/workflow/create", json={}).status_code, 401)

    def test_an_invalid_token_is_401(self):
        self.assertEqual(self.client.get("/api/workflow/", headers=bearer("expired")).status_code, 401)

    def test_any_valid_token_can_read(self):
        for path in ("/api/workflow/", "/api/workflow/metadata", "/api/workflow/builds"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=bearer("viewer")).status_code, 200)

    def test_writes_need_admin_or_researcher(self):
        writes = [
            ("post", "/api/workflow/create"), ("post", "/api/workflow/upload-source"),
            ("post", "/api/workflow/probe-source"), ("post", "/api/workflow/x/annotation"),
            ("post", "/api/workflow/x/build"), ("get", "/api/workflow/x/build"),
            ("get", "/api/workflow/x/approval"), ("delete", "/api/workflow/x"),
        ]
        for method, path in writes:
            with self.subTest(path=path, method=method):
                r = getattr(self.client, method)(path, headers=bearer("viewer"))
                self.assertEqual(r.status_code, 403, r.text)
                r = getattr(self.client, method)(path, headers=bearer("researcher"))
                self.assertNotIn(r.status_code, (401, 403), r.text)


if __name__ == "__main__":
    unittest.main()
