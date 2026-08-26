# Walkthrough

`_create_sds_output` now writes generated dataset keys using
`assay_{assay_id}/{timestamp}/{dataset_name}`.
This keeps assay ID and timestamp in separate path segments, improving browseability in MinIO.
The assay-run regression fixture was updated to match the new prefix shape.
