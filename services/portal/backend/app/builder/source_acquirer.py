"""SourceAcquirer abstraction — strategy for "step 1" of the build pipeline.

Each acquirer encapsulates how to materialize a project_dir on disk for one
source_type. Adding a new source_type (gitlab, bitbucket, generic git, ...)
means adding a new SourceAcquirer subclass and registering it via the
``@SourceAcquirer.register("...")`` decorator, without touching
build_tool.py / build_workflow.py.

Token handling contract (enforced by acquirers that consume `spec.token`):
- token is passed through SourceSpec, NEVER stored on the acquirer instance
  beyond the acquire() call lifetime
- token MUST NOT be embedded in subprocess command line / URL — use
  GIT_ASKPASS via `_clone_with_token`
- token MUST NOT be serialized to logs — use safe_dump from logger module;
  PAT mask filter on root handlers is the last-line-of-defense
- token MUST NOT be persisted to DB
- token characters are validated to `[A-Za-z0-9_-]` so we never need shell
  escaping (matches all major provider PAT formats)
"""
from __future__ import annotations

import os
import platform
import re
import stat
import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Type
from urllib.parse import urlparse, urlunparse

from app.builder.logger import get_logger
from app.utils.builder_utils import clone_repository, inspect_uploaded_source
from app.utils.utils import force_rmtree

logger = get_logger(__name__)


# Personal Access Tokens across GitHub / GitLab / Bitbucket are alphanumeric
# plus `_` / `-`. Validating at the boundary means we never need to shell-
# escape and we fail fast on obviously malformed tokens (e.g. user pasted
# whole curl line by accident).
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


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
    # `repr=False` so accidental `repr(spec)` in logs cannot leak the value.
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


# --- Token-auth git helpers (shared by GitLab / Bitbucket / generic / private GitHub) ---

def _validate_token(token: str) -> None:
    if not token or not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError(
            "token contains characters outside [A-Za-z0-9_-] or is empty"
        )


def _write_askpass_script(scratch_dir: Path, token: str) -> Path:
    """Write a one-shot GIT_ASKPASS script that echoes ``token`` when invoked.

    The script is the only place on disk where the token materializes while
    the clone runs; caller MUST delete it in a finally block. Token is
    validated before this point so no shell escaping is needed.
    """
    if platform.system() == "Windows":
        script = scratch_dir / f"askpass_{uuid.uuid4().hex}.bat"
        # CRLF for cmd.exe; @echo off so the echoed line is the only output.
        script.write_text(f"@echo off\r\necho {token}\r\n", encoding="ascii")
    else:
        script = scratch_dir / f"askpass_{uuid.uuid4().hex}.sh"
        script.write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{token}'\n",
            encoding="ascii",
        )
        script.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return script


def _inject_username_in_url(url: str, username: str) -> str:
    """Insert ``username@`` into URL netloc if no userinfo present.

    git uses the userinfo to phrase its credential prompt; askpass then
    supplies the password. The token NEVER enters the URL — only the
    (non-secret) username does, so the URL remains safe to log.
    """
    parsed = urlparse(url)
    if parsed.username is not None:
        return url
    return urlunparse(parsed._replace(netloc=f"{username}@{parsed.netloc}"))


def _classify_clone_error(stderr: str, returncode: int) -> str:
    """Map git clone stderr to a coarse user-meaningful message.

    Phase 7 will refine and normalize across providers; this is the rough
    first pass good enough for backend RuntimeError messages.
    """
    s = (stderr or "").lower()
    if "authentication failed" in s or "invalid credentials" in s or "could not read username" in s:
        return "Authentication failed — token may be invalid, expired, or lack repo access"
    if "not found" in s or "404" in s:
        return "Repository not found — check URL and that the token has access to it"
    if "could not resolve host" in s:
        return "Network error — could not reach the git server"
    return f"Git clone failed (exit {returncode})"


def _clone_with_token(
    tmp_dir: Path,
    repo_url: str,
    token: str,
    username: str,
    branch: str,
    *,
    shallow: bool = False,
) -> Path:
    """Clone a git repo using GIT_ASKPASS for token-based auth.

    The token never appears in:
      - argv (we don't put `https://oauth2:<token>@host/...` on command line)
      - the URL we log (only the non-secret username is injected)
      - persistent filesystem (askpass script unlinked in finally)

    The PAT mask filter on root log handlers is a last-line-of-defense for
    any token that slips through git's own stderr/stdout (none observed in
    practice, but defense-in-depth).
    """
    _validate_token(token)
    if not repo_url.endswith(".git"):
        repo_url = repo_url + ".git"
    auth_url = _inject_username_in_url(repo_url, username)

    clone_dir = tmp_dir / f"build_{uuid.uuid4().hex[:8]}"
    clone_dir.mkdir(exist_ok=True)
    askpass = _write_askpass_script(tmp_dir, token)

    env = {
        **os.environ,
        "GIT_ASKPASS": str(askpass),
        # Block git's interactive fallback if the askpass script ever fails
        # to produce output — better to error than to hang waiting for stdin.
        "GIT_TERMINAL_PROMPT": "0",
    }

    cmd = ["git", "clone"]
    if shallow:
        cmd += ["--depth", "1"]
    cmd += ["--branch", branch, auth_url, str(clone_dir)]

    logger.info(
        f"Cloning {auth_url} (branch={branch}, shallow={shallow}) with token auth"
    )
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Authenticated git clone failed (exit {e.returncode}): {e.stderr}"
        )
        raise RuntimeError(_classify_clone_error(e.stderr, e.returncode))
    finally:
        try:
            askpass.unlink()
        except OSError:
            logger.warning(f"Failed to remove askpass script {askpass}")

    logger.info(f"Successfully cloned to {clone_dir}")
    return clone_dir


# --- Concrete acquirers ---

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


@SourceAcquirer.register("gitlab")
class GitlabAcquirer(SourceAcquirer):
    """GitLab via git clone — public anonymous, private via PAT.

    Auth contract: ``oauth2`` username + token-as-password supplied through
    GIT_ASKPASS. Token NEVER touches argv, URL, or DB. See module-level
    "Token handling contract".
    """

    # GitLab's documented PAT-over-HTTPS convention: any non-empty username
    # paired with the token as the password. `oauth2` is the canonical choice
    # used by GitLab's own docs and CI.
    _AUTH_USERNAME = "oauth2"

    def acquire(self, spec: SourceSpec) -> Path:
        if not spec.url:
            raise RuntimeError("source_type='gitlab' requires url; got empty/None")

        if spec.token:
            logger.info("Step 1: Cloning private GitLab repository (token auth)...")
            project_dir = _clone_with_token(
                tmp_dir=self.tmp_dir,
                repo_url=spec.url,
                token=spec.token,
                username=self._AUTH_USERNAME,
                branch=spec.branch,
            )
        else:
            logger.info("Step 1: Cloning public GitLab repository...")
            project_dir = clone_repository(self.tmp_dir, spec.url, logger, spec.branch)

        logger.info(f"Repository cloned to: {project_dir}")
        return project_dir

    def probe_metadata(self, spec: SourceSpec) -> Dict[str, Any]:
        """Shallow-clone the repo and return inspect metadata for the form.

        Response shape matches ``inspect_uploaded_source`` so the frontend
        treats local-upload and git-URL probe responses identically. The
        shallow clone is removed before returning — phase 5/probe-source
        endpoint is the only intended caller and it has no need for the
        materialized tree afterward.
        """
        if not spec.url:
            raise RuntimeError("source_type='gitlab' requires url for probe")

        if spec.token:
            project_dir = _clone_with_token(
                tmp_dir=self.tmp_dir,
                repo_url=spec.url,
                token=spec.token,
                username=self._AUTH_USERNAME,
                branch=spec.branch,
                shallow=True,
            )
        else:
            project_dir = clone_repository(
                self.tmp_dir, spec.url, logger, spec.branch, shallow=True
            )

        try:
            return inspect_uploaded_source(project_dir, want_npm=True, want_cwl=True)
        finally:
            force_rmtree(project_dir)
