import logging
from typing import Optional
import sys


def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name or __name__)

    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)

    return logger


def configure_logging(level: int = logging.INFO, logfile: str = "app.log") -> None:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[console_handler, file_handler])
