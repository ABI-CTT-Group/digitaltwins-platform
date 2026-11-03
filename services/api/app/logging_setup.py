"""Send the app's own log records (``app.*``, ``digitaltwins.*``) to stdout at INFO.

uvicorn configures only its ``uvicorn.*`` loggers, which don't propagate to the root logger, so
without this the root stays at WARNING and every INFO line from the app is dropped.
"""
import logging
import sys

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
QUIET = ("botocore", "boto3", "urllib3", "s3transfer")


class _StdoutHandler(logging.StreamHandler):
    """Marks the handler this module added, so configuring twice adds it once."""


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, _StdoutHandler) for h in root.handlers):
        handler = _StdoutHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    for name in QUIET:  # botocore logs a credentials line per client at INFO
        logging.getLogger(name).setLevel(logging.WARNING)
