# Walkthrough

The fix removes identifier stripping at the API trigger boundary and sends canonical SDS IDs to Airflow.
Airflow now forwards `sample_id` into the downloader task.
The downloader reads from sample-level SDS prefixes, matching dataset layout:
`{dataset_uuid}/primary/sub-*/sam-*/...`.
Regression tests cover both payload and prefix behavior.
