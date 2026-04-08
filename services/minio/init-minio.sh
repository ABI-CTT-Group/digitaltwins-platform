#!/bin/sh
sleep 5
mc alias set digitaltwins http://minio:9000 ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}
mc mb --ignore-existing digitaltwins/measurement
mc mb --ignore-existing digitaltwins/model
mc mb --ignore-existing digitaltwins/workflow
mc mb --ignore-existing digitaltwins/tool
mc mb --ignore-existing digitaltwins/process
mc mb --ignore-existing digitaltwins/airflow-workspace
echo 'Buckets created successfully'
exit 0
