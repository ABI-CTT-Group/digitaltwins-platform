import logging
import threading
from collections import OrderedDict, deque
from typing import Optional
from app.builder.logger import get_logger, mask_secrets

logger = get_logger(__name__)

_MAX_LINES_PER_JOB = 5000     # ring buffer upper limit, prevents single job flooding memory
_MAX_JOBS = 64                # max concurrent jobs kept; LRU evicts oldest


class _Job:
    __slots__ = ("lines", "done", "status", "dropped")

    def __init__(self) -> None:
        self.lines: deque[str] = deque(maxlen=_MAX_LINES_PER_JOB)
        self.done = False
        self.status: Optional[str] = None
        self.dropped = 0      # lines evicted by ring buffer (used for offset alignment)


class LogStreamRegistry:
    def __init__(self) -> None:
        self._jobs: "OrderedDict[str, _Job]" = OrderedDict()
        self._cond = threading.Condition()

    def open(self, job_key: str) -> None:
        with self._cond:
            self._jobs[job_key] = _Job()
            self._jobs.move_to_end(job_key)
            while len(self._jobs) > _MAX_JOBS:
                self._jobs.popitem(last=False)
            self._cond.notify_all()

    def append(self, job_key: str, line: str) -> None:
        safe = mask_secrets(line.rstrip("\n"))
        with self._cond:
            job = self._jobs.get(job_key)
            if job is None:
                job = _Job()
                self._jobs[job_key] = job
            if len(job.lines) == job.lines.maxlen:
                job.dropped += 1
            job.lines.append(safe)
            self._cond.notify_all()

    def finish(self, job_key: str, status: str) -> None:
        with self._cond:
            job = self._jobs.get(job_key)
            if job is None:
                job = _Job()
                self._jobs[job_key] = job
            job.done = True
            job.status = status
            self._cond.notify_all()

    def snapshot(self, job_key: str, offset: int):
        """offset = absolute line number already consumed by the caller (including dropped lines)."""
        with self._cond:
            job = self._jobs.get(job_key)
            if job is None:
                return [], offset, True, "gone"
            total = job.dropped + len(job.lines)
            start = max(offset, job.dropped)          # skip lines evicted by ring buffer
            new = list(job.lines)[start - job.dropped:] if start < total else []
            return new, total, job.done, job.status

    def full_text(self, job_key: str) -> str:
        with self._cond:
            job = self._jobs.get(job_key)
            return "\n".join(job.lines) if job else ""

    def exists(self, job_key: str) -> bool:
        with self._cond:
            return job_key in self._jobs


log_registry = LogStreamRegistry()


# ---------------------------------------------------------------------------
# Thread-bound capture of ALL build/deploy logging into the registry.
#
# The build/deploy pipelines emit far more than the two npm/compose subprocess
# streams — clone, vite-config patch, SPARC dataset creation, MinIO upload,
# cleanup, errors — all via `logger.info(...)`. Threading an explicit sink
# only into the subprocess calls captured a fraction of that. Instead, each
# build/deploy runs in its own background thread; we bind that thread to a
# job_key and attach ONE logging handler to the "app" logger. Every record
# emitted from a bound thread (the orchestration steps AND the per-line
# subprocess output, which is also logged) is forwarded to that job's buffer.
# Records from unbound threads (normal request handling) are ignored.
# ---------------------------------------------------------------------------
_thread_jobs: "dict[int, str]" = {}
_thread_jobs_lock = threading.Lock()


def bind_thread_job(job_key: str) -> None:
    """Route this thread's subsequent log records into job_key's buffer."""
    with _thread_jobs_lock:
        _thread_jobs[threading.get_ident()] = job_key


def unbind_thread_job() -> None:
    with _thread_jobs_lock:
        _thread_jobs.pop(threading.get_ident(), None)


class _RegistryLogHandler(logging.Handler):
    """Forward a bound thread's log records to the live log registry."""

    def emit(self, record: logging.LogRecord) -> None:
        with _thread_jobs_lock:
            job_key = _thread_jobs.get(record.thread)
        if not job_key:
            return
        try:
            log_registry.append(job_key, self.format(record))
        except Exception:
            # Never let log forwarding break the emitting code path.
            pass


_registry_handler = _RegistryLogHandler()
_registry_handler.setFormatter(logging.Formatter("%(message)s"))
# Attach to the "app" logger so every app.* record (build_tool, deploy_tool,
# builder_utils, routers) propagates here. Root handlers still print to stdout.
logging.getLogger("app").addHandler(_registry_handler)
