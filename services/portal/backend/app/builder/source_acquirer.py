"""SourceAcquirer abstraction — strategy for "step 1" of the build pipeline.

Each acquirer encapsulates how to materialize a project_dir on disk for one
source_type. Adding a new source_type (gitlab, bitbucket, generic git, ...)
means adding a new SourceAcquirer subclass and registering it via the
``@SourceAcquirer.register("...")`` decorator, without touching
build_tool.py / build_workflow.py.

Token handling contract (applies once private-git acquirers land in phase 2+):
- token is passed through SourceSpec, NEVER stored on the acquirer instance
  beyond the acquire() call lifetime
- token MUST NOT be embedded in subprocess command line — use env / askpass
- token MUST NOT be serialized to logs — use safe_dump from logger module
- token MUST NOT be persisted to DB
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, Optional, Type

from app.builder.logger import get_logger
from app.utils.builder_utils import clone_repository

logger = get_logger(__name__)


@dataclass
class SourceSpec:
    """Carrier for source-acquisition parameters.

    Fields are deliberately optional — different acquirers consume different
    subsets. Validation is the acquirer's responsibility (raise RuntimeError
    on missing required fields with a precise message).
    """
    source_type: str
    url: Optional[str] = None
    branch: str = "main"
    local_archive_path: Optional[str] = None
    # Reserved for phase 2+ private-git providers. `repr=False` so accidental
    # `repr(spec)` in logs cannot leak the value.
    token: Optional[str] = field(default=None, repr=False)


class SourceAcquirer(ABC):
    """Strategy for acquiring source code into a local project_dir."""

    _registry: ClassVar[Dict[str, Type["SourceAcquirer"]]] = {}

    def __init__(self, tmp_dir: Path):
        self.tmp_dir = tmp_dir

    @classmethod
    def register(cls, source_type: str):
        def deco(subcls: Type["SourceAcquirer"]) -> Type["SourceAcquirer"]:
            cls._registry[source_type] = subcls
            return subcls
        return deco

    @classmethod
    def for_type(cls, source_type: str, tmp_dir: Path) -> "SourceAcquirer":
        try:
            subcls = cls._registry[source_type]
        except KeyError:
            raise ValueError(
                f"Unknown source_type: {source_type!r} "
                f"(registered: {sorted(cls._registry.keys())})"
            )
        return subcls(tmp_dir)

    @abstractmethod
    def acquire(self, spec: SourceSpec) -> Path:
        """Materialize source on disk and return the project_dir.

        The returned path is the directory the build pipeline (steps 2+)
        operates on. Cleanup is the caller's responsibility (via
        ``remove_tmp_folder`` once the build finishes).
        """
        ...


@SourceAcquirer.register("github")
class GithubAcquirer(SourceAcquirer):
    """Public GitHub via anonymous git clone.

    Phase 1: zero behavior change vs the prior inline branch in
    build_tool.py / build_workflow.py — same ``git clone --branch <b>`` call
    via ``clone_repository``. Private GitHub will be handled in a later
    phase (either here once token plumbing exists, or via a dedicated
    ``github_private`` acquirer).
    """

    def acquire(self, spec: SourceSpec) -> Path:
        if not spec.url:
            raise RuntimeError("source_type='github' requires url; got empty/None")
        logger.info("Step 1: Cloning repository...")
        project_dir = clone_repository(self.tmp_dir, spec.url, logger, spec.branch)
        logger.info(f"Repository cloned to: {project_dir}")
        return project_dir


@SourceAcquirer.register("local")
class LocalAcquirer(SourceAcquirer):
    """Locally uploaded archive — staging dir already extracted at upload time."""

    def acquire(self, spec: SourceSpec) -> Path:
        if not spec.local_archive_path:
            raise RuntimeError("source_type='local' but local_archive_path is missing")
        project_dir = Path(spec.local_archive_path)
        if not project_dir.exists() or not project_dir.is_dir():
            raise RuntimeError(f"Local staging dir not found: {project_dir}")
        logger.info("Step 1: Using uploaded local archive...")
        logger.info(f"Using uploaded source from: {project_dir}")
        return project_dir
