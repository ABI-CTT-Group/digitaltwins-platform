"""
workflow_9000 — the "CPU Burn Assay" workflow, launched from the portal.

Unlike cpu_burn_primes (a standalone DAG triggered straight from the Airflow UI),
this is a real `workflow_<seek_id>` DAG: assays.py's run_assay() triggers it once
PER discovered sample, passing dag_run.conf built from that sample's real,
registered dataset row (see `services/api/digitaltwins-api/app/routers/assays.py`
_trigger_dag / _discover_samples). workflow_seek_id (9000) is not a real SEEK
Workflow object and is never validated by SEEK -- it only has to match the number
in this file's dag_id, which is all assays.py needs to find it.

What it does, end to end:
  1. Logs the subject/sample/dataset identity dag_run.conf carries -- this IS the
     "read from a real dataset" step. The actual sample discovery (which subject/
     sample/dataset this run is for) already happened in Postgres before the DAG
     was triggered; re-reading the source imaging files here would be real image-
     processing work, out of scope for what this DAG demonstrates.
  2. Burns CPU on the `remote` queue for a fixed duration, partitioning the search
     for primes across `parallelism` child processes (each takes a disjoint
     residue class mod parallelism, so they do not duplicate work) -- same
     daemonic-process-can't-fork-children constraint as cpu_burn_primes, so
     workers are spawned with `subprocess`, not `multiprocessing`.
  3. Writes the merged, sorted list of primes found to primes.txt, uploaded via
     plain boto3 (not the digitaltwins-api package -- that is not guaranteed
     importable inside Airflow's own environment) to every path in
     dag_run.conf['output_prefixes'] (one per configured assay output; in
     practice there is exactly one, "primes_output", for this assay).

Hardcoded to queue="remote" (not the shared `compute_queue` Airflow Variable
cpu_burn_primes reads) -- this DAG's whole purpose is proving the remote
compute path, so there's no "run it locally instead" case worth supporting here.

Viewing the result: open a notebook in Jupyter and read the object straight out
of MinIO with boto3/minio-py -- same bucket+prefix the portal's own "download
results" button (GET /assays/{id}/workspace/dataset/download) uses. See
util/populate-cpu-burn-assay.sh's own summary output for the exact snippet.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

from airflow.decorators import dag, task

log = logging.getLogger(__name__)

# Each child prints "n\n" for every prime it finds in its residue class, until the
# duration elapses. Partitioning by residue class mod `nproc` (starting each child
# at 2 + its index) means the children never re-check the same candidate.
_CHILD_SRC = r"""
import sys, time
duration, nproc, offset = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
deadline = time.monotonic() + duration
n = 2 + offset
while time.monotonic() < deadline:
    for _ in range(500):        # a block of work between (non-free) clock reads
        is_prime = n > 1
        i = 2
        while i * i <= n:
            if n % i == 0:
                is_prime = False
                break
            i += 1
        if is_prime:
            print(n, flush=True)
        n += nproc
"""


@dag(
    dag_id="workflow_9000",
    dag_display_name="CPU Burn Assay workflow",
    description="Demo assay-launched workflow: burns CPU on the remote worker and writes a prime listing to MinIO.",
    schedule=None,                 # only ever triggered via the assay Run path
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["cpu-burn-assay", "demo"],
    params={
        "duration_seconds": 60,
        "parallelism": 4,
    },
)
def workflow_9000() -> None:

    @task
    def log_input(**context) -> dict:
        conf = context["dag_run"].conf or {}
        log.info(
            "CPU Burn Assay run %s (index %s): subject=%s sample=%s dataset=%s sample_type=%s bucket=%s",
            conf.get("run_id"), conf.get("run_index"), conf.get("subject_id"),
            conf.get("sample_id"), conf.get("dataset_uuid"), conf.get("sample_type"),
            conf.get("bucket"),
        )
        return conf

    @task(queue="remote")
    def burn_and_write(conf: dict, **context) -> dict:
        import boto3

        params = context.get("params") or {}
        duration = int(params.get("duration_seconds", 60))
        nproc = max(1, int(params.get("parallelism", 4)))

        host = os.uname().nodename
        log.info("Burning %d core(s) for %ds on %s for subject=%s sample=%s",
                  nproc, duration, host, conf.get("subject_id"), conf.get("sample_id"))

        procs = [
            subprocess.Popen(
                [sys.executable, "-c", _CHILD_SRC, str(duration), str(nproc), str(i)],
                stdout=subprocess.PIPE, text=True,
            )
            for i in range(nproc)
        ]

        primes: set[int] = set()
        for p in procs:
            out, _ = p.communicate()
            for line in out.splitlines():
                try:
                    primes.add(int(line))
                except ValueError:
                    pass  # a stray line from a child doesn't sink the run

        sorted_primes = sorted(primes)
        log.info("Done: found %d primes on %s", len(sorted_primes), host)

        body = "\n".join(str(p) for p in sorted_primes).encode() + b"\n"

        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ["MINIO_ENDPOINT"],
            aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
            aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
        )
        bucket = conf.get("bucket")
        output_prefixes = conf.get("output_prefixes") or {}
        written = []
        for out_name, prefix in output_prefixes.items():
            key = f"{prefix}/primes.txt"
            s3.put_object(Bucket=bucket, Key=key, Body=body)
            written.append(f"s3://{bucket}/{key}")
            log.info("Wrote %s (%d primes) -> %s", out_name, len(sorted_primes), key)

        return {"primes_found": len(sorted_primes), "written": written}

    burn_and_write(log_input())


workflow_9000()
