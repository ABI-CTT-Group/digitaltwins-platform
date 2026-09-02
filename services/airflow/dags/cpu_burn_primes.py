"""
cpu_burn_primes — a standalone, GUI-triggerable test workflow.

It burns CPU for a few minutes by counting primes with trial division
(deliberately NOT a sieve — the point is to keep the cores busy). Unlike the
`workflow_<seek_id>` DAGs, this takes NO external inputs and is NOT tied to a SEEK
assay/workflow, so you trigger it straight from the Airflow UI (the ▶ button, or
"Trigger DAG w/ config" to change the duration / core count).

Why it exists:
  * prove the Airflow trigger path end-to-end without the assay/registration chain, and
  * generate a visible, bounded CPU load — handy for exercising the remote compute
    node and watching it show up in Grafana (node-exporter CPU + this task's logs).

Routing: it reads the same `compute_queue` Airflow Variable the real workflows use.
Leave it "default" to run on the portal's local worker; set it to "remote" (once a
remote worker actually serves that queue) to push the burn onto the compute node.

Multi-core note: Airflow runs a task inside a DAEMON process, and daemon processes
may not fork `multiprocessing` children ("daemonic processes are not allowed to have
children"). So we fan out across cores with `subprocess` — independent OS processes —
which the daemon restriction does not apply to.

Tunables (edit in the "Trigger DAG w/ config" form):
  duration_seconds : wall-clock seconds to burn   (default 180 = 3 min)
  parallelism      : number of CPU cores to load  (default 4)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from airflow.decorators import dag, task
from airflow.models import Variable

log = logging.getLogger(__name__)

# Parse-time read on the dag-processor (full Airflow available here). Sets which
# Celery queue the burn task lands on — same lever as the workflow_* DAGs.
COMPUTE_QUEUE = Variable.get("compute_queue", default_var="default")

# Self-contained CPU burn run in each child subprocess: count primes by trial
# division until `argv[1]` wall-clock seconds elapse, then print the count.
_CHILD_SRC = r"""
import sys, time
deadline = time.monotonic() + float(sys.argv[1])
count, n = 0, 2
while time.monotonic() < deadline:
    for _ in range(2000):          # a block of work between (non-free) clock reads
        is_prime = n > 1
        i = 2
        while i * i <= n:
            if n % i == 0:
                is_prime = False
                break
            i += 1
        if is_prime:
            count += 1
        n += 1
print(count)
"""


@dag(
    dag_id="cpu_burn_primes",
    dag_display_name="CPU burn (prime counting)",
    description="Standalone CPU-burn test workflow — counts primes for a few minutes.",
    schedule=None,                    # trigger-only, no schedule
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    is_paused_upon_creation=False,    # ready to trigger immediately (overrides the global "paused" default)
    tags=["test", "cpu", "benchmark"],
    params={
        "duration_seconds": 180,      # 3 minutes
        "parallelism": 4,             # cores to load
    },
)
def cpu_burn_primes() -> None:

    @task(queue=COMPUTE_QUEUE)
    def burn(**context) -> dict:
        params = context.get("params") or {}
        duration = int(params.get("duration_seconds", 180))
        nproc = max(1, int(params.get("parallelism", 4)))

        host = os.uname().nodename
        cpu_count = os.cpu_count() or 1
        log.info("Burning %d core(s) for %ds on %s (%d CPU present) [queue=%s]",
                 nproc, duration, host, cpu_count, COMPUTE_QUEUE)

        start = time.monotonic()
        # Fan out with subprocess (NOT multiprocessing — Airflow's task is daemonic).
        procs = [
            subprocess.Popen([sys.executable, "-c", _CHILD_SRC, str(duration)],
                             stdout=subprocess.PIPE, text=True)
            for _ in range(nproc)
        ]

        # heartbeat so the task log shows life while it burns
        while any(p.poll() is None for p in procs):
            log.info("... burning, %.0fs / %ds elapsed", time.monotonic() - start, duration)
            time.sleep(15)

        total = 0
        for p in procs:
            out, _ = p.communicate()
            try:
                total += int((out or "0").strip().splitlines()[-1])
            except (ValueError, IndexError):
                pass  # a child that produced no clean count doesn't sink the run

        result = {
            "primes_counted": total,
            "cores_used": nproc,
            "duration_seconds": round(time.monotonic() - start, 1),
            "host": host,
            "queue": COMPUTE_QUEUE,
        }
        log.info("Done: %s", result)
        return result

    @task
    def report(summary: dict) -> None:
        log.info(
            "CPU burn complete on %s (queue=%s): counted %s primes across %s core(s) in %ss",
            summary["host"], summary["queue"], summary["primes_counted"],
            summary["cores_used"], summary["duration_seconds"],
        )

    report(burn())


cpu_burn_primes()
