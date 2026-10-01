#!/bin/sh
sleep 5
mc alias set digitaltwins http://minio:9000 ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}
mc mb --ignore-existing digitaltwins/measurements
mc mb --ignore-existing digitaltwins/models
mc mb --ignore-existing digitaltwins/workflows
mc mb --ignore-existing digitaltwins/tools
mc mb --ignore-existing digitaltwins/tool-builds
mc mb --ignore-existing digitaltwins/airflow-workspace

# Set Public Access Policy
mc anonymous set public digitaltwins/tools
# Portal test builds of tools not yet approved (loaded by the browser like approved ones)
mc anonymous set download digitaltwins/tool-builds

echo 'Buckets created successfully'
exit 0
