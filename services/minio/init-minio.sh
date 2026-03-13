#!/bin/sh
sleep 5
mc alias set digitaltwins http://minio:9000 ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}
mc mb --ignore-existing digitaltwins/measurements
mc mb --ignore-existing digitaltwins/models
mc mb --ignore-existing digitaltwins/workflows
mc mb --ignore-existing digitaltwins/tools
mc mb --ignore-existing digitaltwins/processes
echo 'Buckets created successfully'
exit 0
