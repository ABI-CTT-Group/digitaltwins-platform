"""Re-push measurement datasets whose FHIR file URLs name an old address of this API, from inside the api container.

    python -m digitaltwins.cli.repush_fhir_urls [--dry-run]

A measurement dataset's FHIR resources link its files as
``<API_PUBLIC_URL>/datasets/<uuid>/files/primary/...``, in HAPI, in its stored annotation and in its
fhir.json. After the API's public URL changes (e.g. /digitaltwins-api became /api), this finds the
datasets pushed with another base and re-pushes each with the FHIR push job, which recomputes the URLs
from the current API_PUBLIC_URL and replaces all three. A dataset whose push is in progress is skipped;
run again once it finishes. Datasets never pushed, or whose push failed, get the new URLs on their next push.

Re-pushing re-downloads each dataset from MinIO and gives its HAPI resources new ids.

Exit codes: 0 ok (or nothing to do), 1 a re-push failed.
"""
import argparse
import json
import sys

from ..core.connection import Connection
from ..measurements import jobs

IN_PROGRESS = ("pending", "pushing")


def _connect():
    conn, _ = Connection().connect()
    return conn


def is_stale(descriptions, dataset_uuid: str, base: str) -> bool:
    """Whether any of the dataset's file URLs is not under ``base``."""
    text = json.dumps(descriptions)
    files = f"/datasets/{dataset_uuid}/files/primary"
    return text.count(files) != text.count(base.rstrip("/") + files)


def candidates(conn) -> list:
    """Annotated measurement datasets with a push done or in progress, oldest first."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT d.dataset_uuid, d.dataset_name, d.fhir_status, a.descriptions "
            "FROM dataset d JOIN dataset_fhir_annotation a USING (dataset_uuid) "
            "WHERE COALESCE(d.workflow_type, '') = '' AND d.category NOT IN ('tools', 'models') "
            "AND d.fhir_status IN ('completed', 'pending', 'pushing') "
            "ORDER BY d.created_at"
        )
        rows = [{"dataset_uuid": str(r[0]), "dataset_name": r[1], "fhir_status": r[2], "descriptions": r[3]}
                for r in cur.fetchall()]
    conn.commit()
    return rows


def _fhir_status(conn, dataset_uuid: str):
    with conn.cursor() as cur:
        cur.execute("SELECT fhir_status, fhir_failure_message FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))
        row = cur.fetchone()
    conn.commit()
    return row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m digitaltwins.cli.repush_fhir_urls", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="list the datasets to re-push; change nothing")
    args = parser.parse_args(argv)

    base = jobs.public_base()
    print(f"  API public URL: {base}")
    conn = _connect()
    try:
        stale = [r for r in candidates(conn) if is_stale(r["descriptions"], r["dataset_uuid"], base)]
        if not stale:
            print("  Nothing to re-push")
            return 0
        if args.dry_run:
            for r in stale:
                print(f"  {r['dataset_name']} ({r['dataset_uuid']}): {r['fhir_status']}")
            print(f"  Would re-push {len(stale)} dataset(s)")
            return 0

        pushed = failed = skipped = 0
        for r in stale:
            label = f"{r['dataset_name']} ({r['dataset_uuid']})"
            if r["fhir_status"] in IN_PROGRESS:
                print(f"  - {label} skipped: a FHIR push is in progress")
                skipped += 1
                continue
            try:
                jobs.run_fhir_push_job(r["dataset_uuid"])
                status, message = _fhir_status(conn, r["dataset_uuid"])
            except Exception as e:  # keep going: one dataset's failure must not strand the rest
                status, message = "failed", str(e)
            if status == "completed":
                print(f"  ✓ {label} re-pushed")
                pushed += 1
            else:
                print(f"  ✗ {label}: {message or status}", file=sys.stderr)
                failed += 1
        print(f"  {pushed} re-pushed, {failed} failed, {skipped} skipped")
        return 1 if failed else 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
