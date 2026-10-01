"""Core orchestrator for dataset deletion.

Coordinates Postgres and MinIO deletions within a single transaction
so that either everything succeeds or everything is rolled back.
"""

import os
import logging
import shutil
from typing import Optional

import psycopg2

from dotenv import load_dotenv

load_dotenv()

from ..utils.config_loader import is_truthy

logger = logging.getLogger(__name__)


class DatasetInUseError(RuntimeError):
    """The delete was refused: a workflow without ``delete_tools``, or a tool a workflow still runs.

    ``details`` carries ``tools`` (a workflow's tool datasets) or ``workflows``
    (the workflows that run the tool), for the client to show or confirm.
    """

    def __init__(self, message: str, details: dict):
        super().__init__(message)
        self.details = details


class Deleter(object):
    def __init__(self, api_token: Optional[str] = None):
        # The caller's Keycloak token, used to delete a tool's SEEK Workflow as that user.
        self._api_token = api_token
        self._postgres_enabled = is_truthy(os.getenv("POSTGRES_ENABLED"))
        self._minio_enabled = is_truthy(os.getenv("MINIO_ENABLED"))

        self._postgres_deleter = None
        self._minio_deleter = None

        if self._postgres_enabled:
            from ..postgres.deleter import Deleter as PostgresDeleter
            self._postgres_deleter = PostgresDeleter()

        if self._minio_enabled:
            from ..minio.deleter import Deleter as MinioDeleter
            self._minio_deleter = MinioDeleter()

    def delete_dataset(self, dataset_uuid: str, delete_tools: Optional[bool] = None) -> dict:
        """Delete a dataset from Postgres and MinIO.

        Args:
            dataset_uuid: The UUID of the dataset to delete.
            delete_tools: Required for a workflow dataset: whether the tool
                datasets its steps run are deleted too (after the workflow).

        Returns:
            A summary dict with keys ``dataset_uuid``, ``minio_objects_deleted``,
            ``fhir_resources_deleted``, ``seek_workflow_deleted`` and
            ``tools_deleted`` (the deleted tool datasets' UUIDs).

        Raises:
            ValueError: If the dataset UUID does not exist in Postgres.
            DatasetInUseError: For a workflow without ``delete_tools``, or a
                tool that a workflow still runs; nothing is deleted.
            RuntimeError: If MinIO deletion fails (Postgres is rolled back).
        """
        # 1. Check existence, and that no workflow link stands in the way
        links = {"workflow_type": None, "tools": [], "used_by": []}
        if self._postgres_enabled and self._postgres_deleter:
            if not self._postgres_deleter.dataset_exists(dataset_uuid):
                raise ValueError(f"Dataset with UUID '{dataset_uuid}' not found")
            links = self._postgres_deleter.workflow_links(dataset_uuid)
            if links["used_by"]:
                names = ", ".join(w["dataset_name"] or w["dataset_uuid"] for w in links["used_by"])
                raise DatasetInUseError(f"Tool dataset '{dataset_uuid}' is used by workflow(s): {names}; "
                                        "delete the workflow first", {"workflows": links["used_by"]})
            if links["workflow_type"] and delete_tools is None:
                raise DatasetInUseError(f"Workflow dataset '{dataset_uuid}' runs {len(links['tools'])} tool "
                                        "dataset(s); pass delete_tools=true or false", {"tools": links["tools"]})

        # 2. Open a Postgres transaction
        conn: Optional[psycopg2.extensions.connection] = None
        minio_deleted = 0
        cleanup = {"fhir_status": "none", "subject_uuids": [], "upload_ids": [], "category": None, "seek_id": None,
                   "workflow_type": None}

        try:
            if self._postgres_enabled and self._postgres_deleter:
                conn = self._postgres_deleter.connect()
                conn.autocommit = False
                cur = conn.cursor()

            # 3. Delete MinIO objects first
            if self._minio_enabled and self._minio_deleter:
                minio_deleted = self._minio_deleter.delete_dataset_objects(dataset_uuid)
                logger.info("Deleted %d MinIO object(s) for dataset %s", minio_deleted, dataset_uuid)

            # 4. Delete Postgres rows
            if conn:
                cleanup = self._postgres_deleter.get_cleanup_info(cur, dataset_uuid)
                self._postgres_deleter.delete_dataset(cur, dataset_uuid)

            # 5. Commit
            if conn:
                conn.commit()
                logger.info("Postgres transaction committed for dataset %s", dataset_uuid)

        except Exception:
            if conn:
                conn.rollback()
                logger.error("Postgres transaction rolled back for dataset %s", dataset_uuid)
            raise
        finally:
            if conn:
                conn.close()

        # 6. Outside Postgres, best-effort: FHIR resources, a tool's / workflow's SEEK Workflow, local copies.
        fhir_deleted = (_delete_fhir_resources(dataset_uuid, cleanup["category"], cleanup["subject_uuids"],
                                               cleanup["workflow_type"])
                        if cleanup["fhir_status"] != "none" else {})
        seek_deleted = _delete_seek_workflow(dataset_uuid, cleanup["category"], cleanup["seek_id"], self._api_token,
                                             cleanup["workflow_type"])
        _remove_local_copies(dataset_uuid, cleanup["upload_ids"])

        # 7. A workflow's tools, once nothing links to them any more (its link rows went with it).
        tools_deleted = []
        if delete_tools:
            for tool in links["tools"]:
                self.delete_dataset(tool["dataset_uuid"])
                tools_deleted.append(tool["dataset_uuid"])

        return {
            "dataset_uuid": dataset_uuid,
            "minio_objects_deleted": minio_deleted,
            "fhir_resources_deleted": fhir_deleted,
            "seek_workflow_deleted": seek_deleted,
            "tools_deleted": tools_deleted,
        }


def _delete_fhir_resources(dataset_uuid: str, category: Optional[str], subject_uuids: list,
                           workflow_type: Optional[str] = None) -> dict:
    """Remove the dataset's HAPI FHIR resources; log and carry on if HAPI is unreachable."""
    from .. import tools
    from ..measurements import fhir_service
    from ..tools import fhir as tool_fhir
    from ..workflows import fhir as workflow_fhir

    try:
        if workflow_type:
            removed = workflow_fhir.delete(dataset_uuid, fhir_service.get_fhir_rest())
            return {"PlanDefinition": removed} if removed else {}
        if category == tools.CATEGORY:
            removed = tool_fhir.delete(dataset_uuid, fhir_service.get_fhir_rest())
            return {"ActivityDefinition": removed} if removed else {}
        return fhir_service.delete_dataset_fhir_resources(dataset_uuid, subject_uuids, fhir_service.get_fhir_rest())
    except Exception as exc:
        logger.warning("FHIR cleanup failed for dataset %s: %s", dataset_uuid, exc)
        return {}


def _delete_seek_workflow(dataset_uuid: str, category: Optional[str], seek_id: Optional[str],
                          api_token: Optional[str], workflow_type: Optional[str] = None) -> bool:
    """Remove a tool or workflow dataset's SEEK Workflow; log and carry on if SEEK refuses or is unreachable."""
    from .. import tools

    if (category != tools.CATEGORY and not workflow_type) or not seek_id:
        return False
    if not api_token:
        logger.warning("No token to delete SEEK workflow %s of dataset %s", seek_id, dataset_uuid)
        return False
    from ..seek.writer import Writer

    try:
        Writer(api_token=api_token).delete_workflow(seek_id)
    except Exception as exc:
        logger.warning("SEEK cleanup failed for dataset %s (workflow %s): %s", dataset_uuid, seek_id, exc)
        return False
    return True


def _remove_local_copies(dataset_uuid: str, upload_ids: list) -> None:
    from ..measurements.staging import dataset_dir, staging_root

    for path in [dataset_dir(u) for u in upload_ids] + [staging_root() / "downloads" / dataset_uuid]:
        shutil.rmtree(path, ignore_errors=True)
