# Implementation plan

1. Keep canonical SDS identifiers in assay DAG payloads (`sub-*`, `sam-*`).
2. Thread `sample_id` through `workflow_image_conversion` into `tool_download_samples`.
3. Build MinIO source prefix at sample scope.
4. Add regression tests for both config payload and downloader prefix behavior.
