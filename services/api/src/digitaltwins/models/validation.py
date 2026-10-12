"""Structural check for a model dataset: generic SDS, no framework-specific rules."""
from pathlib import Path

from ..measurements.validation import resolve_project_root


def validate_model_structure(staging: Path) -> tuple[bool, str]:
    """A model dataset needs ``dataset_description.xlsx`` (or ``.json``) at its root
    and a ``primary/`` folder holding at least one file, at any depth.

    Returns (ok, message); on failure the message is fit for a 400 response.
    """
    staging = Path(staging)
    if not staging.is_dir():
        return (False, f"Staging directory not found: {staging}")
    root = resolve_project_root(staging)
    if not any((root / name).exists() for name in ("dataset_description.xlsx", "dataset_description.json")):
        return (False, "Missing dataset_description.xlsx (or .json) at the dataset root. "
                       "Expected a SPARC (SDS) model dataset structure.")
    primary = root / "primary"
    if not primary.is_dir():
        return (False, "Missing primary/ subdirectory at the dataset root; it holds the model files.")
    if not any(p.is_file() for p in primary.rglob("*")):
        return (False, "primary/ contains no model files.")
    return (True, "")
