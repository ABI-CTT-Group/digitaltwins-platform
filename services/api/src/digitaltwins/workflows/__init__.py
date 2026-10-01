"""Workflow dataset ingest: validation, and registration of the workflow and its tools.

A workflow *definition* is a dataset of this category with ``workflow_type`` set;
the category (and MinIO bucket) is shared with assay workspace outputs.
"""

# Dataset category, and so MinIO bucket, of workflow datasets.
CATEGORY = "workflows"

WORKFLOW_TYPES = ("script", "notebook", "gui")
