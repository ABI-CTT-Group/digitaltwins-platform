import json
import logging
import re
import sys
from typing import Any, Mapping, Optional


# Keys that, when present in a dict being logged via `safe_dump`, are masked
# rather than dumped. Defense-in-depth alongside `_PatMaskingFilter` —
# explicit-by-name catches token-shaped values that don't fit the PAT regex
# (e.g. short basic-auth passwords) and signals intent at the call site.
_SENSITIVE_KEYS = frozenset({
    "token", "password", "secret", "api_key", "apikey", "access_token",
    "private_key", "auth", "authorization", "credential", "credentials",
})


def safe_dump(d: Mapping[str, Any], **kwargs: Any) -> str:
    """JSON-dump a mapping for logging with sensitive keys masked.

    Pair with `_PatMaskingFilter` (catches PAT-shaped strings in arbitrary
    positions) for defense-in-depth.
    """
    safe = {
        k: "***" if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS else v
        for k, v in d.items()
    }
    kwargs.setdefault("default", str)
    return json.dumps(safe, **kwargs)


class _PatMaskingFilter(logging.Filter):
    """Mask Personal Access Token-shaped strings in log records.

    Catches GitHub (`ghp_...`, `github_pat_...`), GitLab (`glpat-...`),
    Bitbucket app passwords, and any 20+ char `[A-Za-z0-9_-]` run. This is
    the last-line-of-defense — primary defense is `safe_dump` at the call
    site, plus never passing tokens into log-bound dicts in the first place.
    """
    _PAT_RE = re.compile(r"\b[A-Za-z0-9_\-]{20,}\b")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            masked = self._PAT_RE.sub(self._mask, msg)
            if masked != msg:
                # Replace the formatted message; clear args so handlers
                # don't re-format and re-introduce the unmasked value.
                record.msg = masked
                record.args = None
        except Exception:
            # Never let masking break logging — fail open on filter errors.
            pass
        return True

    @staticmethod
    def _mask(m: "re.Match[str]") -> str:
        s = m.group(0)
        if len(s) <= 8:
            return "***"
        return f"{s[:4]}***{s[-2:]}"


def _ensure_mask_on_root_handlers() -> None:
    for h in logging.root.handlers:
        if not any(isinstance(f, _PatMaskingFilter) for f in h.filters):
            h.addFilter(_PatMaskingFilter())


def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name or __name__)

    if not logger.handlers and not logging.root.handlers:
        logging.basicConfig(level=logging.INFO)

    _ensure_mask_on_root_handlers()

    return logger


def configure_logging(level: int = logging.INFO, logfile: str = "app.log") -> None:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    pat_filter = _PatMaskingFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(pat_filter)

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(pat_filter)

    logging.basicConfig(level=level, handlers=[console_handler, file_handler])
