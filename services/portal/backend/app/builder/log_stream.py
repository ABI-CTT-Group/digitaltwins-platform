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
