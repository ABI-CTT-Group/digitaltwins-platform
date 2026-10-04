"""Postgres deletion operations for datasets."""

import os
import logging

import psycopg2

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Deleter(object):
    def __init__(self):
        self._host = os.getenv("POSTGRES_HOST")
        self._port = os.getenv("POSTGRES_PORT")
        self._database = os.getenv("POSTGRES_DB")
        self._user = os.getenv("POSTGRES_USER")
        self._password = os.getenv("POSTGRES_PASSWORD")

        missing_vars = [
            name
            for name, value in [
                ("POSTGRES_HOST", self._host),
                ("POSTGRES_PORT", self._port),
                ("POSTGRES_DB", self._database),
                ("POSTGRES_USER", self._user),
                ("POSTGRES_PASSWORD", self._password),
            ]
            if not value
        ]
        if missing_vars:
            raise ValueError(
                "Missing required environment variables for PostgreSQL connection: "
                + ", ".join(missing_vars)
            )

    def connect(self):
        """Create and return a new database connection."""
        return psycopg2.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password,
        )

    def dataset_exists(self, dataset_uuid: str) -> bool:
        """Check whether a dataset with the given UUID exists.

        Opens its own short-lived connection so that the existence check
        is independent of any ongoing transaction.
        """
        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM dataset WHERE dataset_uuid = %s",
                (dataset_uuid,),
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    def workflow_links(self, dataset_uuid: str) -> dict:
        """``{workflow_type, tools, used_by}``: a workflow's type and the tool datasets
        its steps run (see ``workflows.pipeline.linked_tools``), and the workflows
        that run this dataset as a tool (``[{dataset_uuid, dataset_name}]``)."""
        from ..workflows.pipeline import linked_tools

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT workflow_type FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))
                row = cur.fetchone()
                cur.execute(
                    "SELECT DISTINCT wt.workflow_dataset_uuid::text, d.dataset_name FROM workflow_tool wt "
                    "JOIN dataset d ON d.dataset_uuid = wt.workflow_dataset_uuid "
                    "WHERE wt.tool_dataset_uuid = %s ORDER BY 1",
                    (dataset_uuid,),
                )
                used_by = [{"dataset_uuid": u, "dataset_name": n} for u, n in cur.fetchall()]
            workflow_type = row[0] if row else None
            return {
                "workflow_type": workflow_type,
                "tools": linked_tools(conn, dataset_uuid) if workflow_type else [],
                "used_by": used_by,
            }
        finally:
            conn.close()

    def get_cleanup_info(self, cur, dataset_uuid: str) -> dict:
        """What lives outside Postgres for this dataset: its FHIR status, subjects
        (the Patients' identifiers), upload sessions, and category + SEEK id + workflow type."""
        cur.execute("SELECT fhir_status, category, seek_id, workflow_type FROM dataset WHERE dataset_uuid = %s",
                    (dataset_uuid,))
        row = cur.fetchone()
        cur.execute("SELECT DISTINCT subject_uuid FROM dataset_mapping WHERE dataset_uuid = %s", (dataset_uuid,))
        subject_uuids = [str(r[0]) for r in cur.fetchall()]
        cur.execute("SELECT upload_id FROM upload_session WHERE dataset_uuid = %s", (dataset_uuid,))
        return {
            "fhir_status": row[0] if row else "none",
            "subject_uuids": subject_uuids,
            "upload_ids": [str(r[0]) for r in cur.fetchall()],
            "category": row[1] if row else None,
            "seek_id": row[2] if row else None,
            "workflow_type": row[3] if row else None,
        }

    def delete_dataset(self, cur, dataset_uuid: str) -> None:
        """Delete all rows linked to *dataset_uuid* using the provided cursor.

        The caller is responsible for managing the transaction (commit /
        rollback) on the connection that owns *cur*.

        Deletion order respects foreign-key constraints:
          dataset_mapping → manifest → dataset_description → annotation /
          upload sessions → dataset, then the dataset's subject / sample rows
          that no other dataset still maps.
        """
        cur.execute(
            "SELECT DISTINCT subject_uuid, sample_uuid FROM dataset_mapping WHERE dataset_uuid = %s",
            (dataset_uuid,),
        )
        pairs = cur.fetchall()
        tables = [
            "dataset_mapping",
            "manifest",
            "dataset_description",
            "dataset_fhir_annotation",
            "upload_session",
            "dataset",
        ]
        for table in tables:
            cur.execute(
                f"DELETE FROM {table} WHERE dataset_uuid = %s",
                (dataset_uuid,),
            )
            logger.info(
                "Deleted %d row(s) from %s for dataset %s",
                cur.rowcount, table, dataset_uuid,
            )
        for table, column, uuids in (
            ("sample", "sample_uuid", sorted({str(sample) for _, sample in pairs})),
            ("subject", "subject_uuid", sorted({str(subject) for subject, _ in pairs})),
        ):
            if not uuids:
                continue
            cur.execute(
                f"DELETE FROM {table} WHERE {column} = ANY(%s::uuid[]) "
                f"AND NOT EXISTS (SELECT 1 FROM dataset_mapping m WHERE m.{column} = {table}.{column})",
                (uuids,),
            )
            logger.info("Deleted %d row(s) from %s for dataset %s", cur.rowcount, table, dataset_uuid)
