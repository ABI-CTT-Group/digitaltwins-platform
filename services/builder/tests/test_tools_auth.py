"""Keycloak on /api/builder/tools: any valid token reads, admin|researcher write, admin deploys.

Run from `services/builder/`:
    python -m pytest tests/test_tools_auth.py
"""
import unittest

from tests.tool_app import bearer, make_client


class ToolsAuthTest(unittest.TestCase):
    def setUp(self):
        self.client = make_client()

    def test_no_token_is_401(self):
        self.assertEqual(self.client.get("/api/builder/tools/").status_code, 401)
        self.assertEqual(self.client.post("/api/builder/tools/create", json={}).status_code, 401)

    def test_an_invalid_token_is_401(self):
        self.assertEqual(self.client.get("/api/builder/tools/", headers=bearer("expired")).status_code, 401)

    def test_any_valid_token_can_read(self):
        self.assertEqual(self.client.get("/api/builder/tools/", headers=bearer("viewer")).status_code, 200)

    def test_writes_need_admin_or_researcher(self):
        writes = [
            ("post", "/api/builder/tools/create"), ("post", "/api/builder/tools/upload-source"), ("post", "/api/builder/tools/probe-source"),
            ("post", "/api/builder/tools/plugin/x/annotation"), ("post", "/api/builder/tools/plugin/x/build"),
            ("get", "/api/builder/tools/plugin/x/build"), ("delete", "/api/builder/tools/plugin/x"),
            ("post", "/api/builder/tools/plugin/x/approval"),
        ]
        for method, path in writes:
            with self.subTest(path=path, method=method):
                r = getattr(self.client, method)(path, headers=bearer("viewer"))
                self.assertEqual(r.status_code, 403, r.text)
                r = getattr(self.client, method)(path, headers=bearer("researcher"))
                self.assertNotIn(r.status_code, (401, 403), r.text)

    def test_deploy_and_debug_are_admin_only(self):
        admin_only = ["/api/builder/tools/plugin/x/deploy", "/api/builder/tools/plugin/deploy/x/execute?command=up",
                      "/api/builder/tools/debug/nginx-config", "/api/builder/tools/test-build"]
        for path in admin_only:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=bearer("researcher")).status_code, 403)
                self.assertNotIn(self.client.get(path, headers=bearer("admin")).status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
