"""Tool Hub launch metadata (test vs approved builds) and deleting a tool from the platform.

Run from `backend/`:
    python -m unittest tests.test_tool_catalogue
"""
import unittest
import uuid

from tests.tool_app import bearer  # noqa: I001  (sets DATABASE_PATH first)
from tests import test_tool_handoff
from app.models.db_model import Plugin, PluginBuild, SessionLocal
from app.router import workflow_tool_plugin


class FakeBucket:
    def __init__(self, keys=()):
        self.keys = set(keys)
        self.deleted = []

    def object_exists(self, key):
        return key in self.keys

    def list_objects(self, prefix=""):
        return [{"Key": k} for k in sorted(self.keys) if k.startswith(prefix)]

    # No bulk delete_objects, deliberately: MinIO rejects multi-object delete without
    # Content-MD5 (boto3 >= 1.36 no longer sends it), so objects go one by one.
    def delete_object(self, key):
        self.deleted.append(key)


class CatalogueTest(test_tool_handoff.HandoffTest):
    def setUp(self):
        super().setUp()
        self.buckets = {"tools": FakeBucket(), "tool-builds": FakeBucket()}
        self._orig_client = workflow_tool_plugin.get_minio_client
        workflow_tool_plugin.get_minio_client = lambda bucket=None: self.buckets[bucket or "tools"]

    def tearDown(self):
        workflow_tool_plugin.get_minio_client = self._orig_client

    def _components(self):
        r = self.client.get("/api/tools/metadata", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        return {c["id"]: c for c in r.json()["components"]}

    def _gui(self):
        with SessionLocal() as db:
            db.get(Plugin, self.plugin_id).label = "GUI"
            db.commit()

    # -- metadata ------------------------------------------------------------

    def test_an_unapproved_gui_build_is_served_from_tool_builds(self):
        self._gui()
        with SessionLocal() as db:
            db.query(PluginBuild).update({"s3_path": "s3://tool-builds/convert_ab12cd34"})
            db.commit()

        path = self._components()[self.plugin_id]["path"]

        self.assertTrue(path.startswith("/tool-builds/convert_ab12cd34/primary/my-app.umd.js?v="), path)

    def test_an_approved_gui_tool_is_served_from_its_platform_dataset(self):
        self._gui()
        self._approve()
        dataset_uuid = self._rows()[0].uuid

        component = self._components()[self.plugin_id]

        self.assertTrue(component["path"].startswith(f"/tools/{dataset_uuid}/primary/my-app.umd.js?v="))
        self.assertEqual((component["uuid"], component["expose"]), (dataset_uuid, "convert_ab12cd34"))

    # -- delete --------------------------------------------------------------

    def _delete(self):
        r = self.client.delete(f"/api/tools/plugin/{self.plugin_id}", headers=bearer("researcher"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _plugin_exists(self):
        with SessionLocal() as db:
            return db.get(Plugin, self.plugin_id) is not None

    def test_deleting_an_approved_tool_deletes_its_platform_dataset(self):
        self._approve()
        dataset_uuid = self._rows()[0].uuid

        self.assertTrue(self._delete()["status"])
        self.assertEqual(self.api.deleted, [dataset_uuid])
        self.assertFalse(self._plugin_exists())

    def test_a_failed_platform_delete_keeps_the_tool(self):
        self._approve()
        self.api.fail_delete = True

        result = self._delete()

        self.assertFalse(result["status"])
        self.assertIn("MinIO unreachable", result["message"])
        self.assertTrue(self._plugin_exists())

    def test_a_dataset_already_gone_counts_as_deleted(self):
        with SessionLocal() as db:
            db.get(Plugin, self.plugin_id).uuid = str(uuid.uuid4())
            db.commit()

        self.assertTrue(self._delete()["status"])
        self.assertFalse(self._plugin_exists())

    def test_a_legacy_placeholder_uuid_is_not_sent_to_the_platform(self):
        with SessionLocal() as db:
            db.get(Plugin, self.plugin_id).uuid = f"sparc-tool-${uuid.uuid4()}"
            db.commit()

        self.assertTrue(self._delete()["status"])
        self.assertEqual(self.api.deleted, [])

    def test_test_build_objects_are_removed_from_their_bucket(self):
        with SessionLocal() as db:
            db.query(PluginBuild).update({"s3_path": "s3://tool-builds/convert_ab12cd34"})
            db.commit()
        self.buckets["tool-builds"].keys.add("convert_ab12cd34/primary/my-app.umd.js")

        self.assertTrue(self._delete()["status"])
        self.assertEqual(self.buckets["tool-builds"].deleted, ["convert_ab12cd34/primary/my-app.umd.js"])


# The inherited handoff tests already ran in test_tool_handoff.
for name in [n for n in dir(test_tool_handoff.HandoffTest) if n.startswith("test_")]:
    setattr(CatalogueTest, name, None)


if __name__ == "__main__":
    unittest.main()
