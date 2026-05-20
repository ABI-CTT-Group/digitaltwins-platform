#!/bin/bash
# Back up the data volumes of importance to us

set -euo pipefail

DOCKER_VOLS_DIR=/var/lib/docker/volumes
BASE_DIR=~/digitaltwins-platform
ENV_FILE=$BASE_DIR/.env

now=$(date +%Y%m%d%H%M)
mkdir $now
cd $now

cd $BASE_DIR
docker compose down
cd -

grep "^[[:blank:]]*SEEK_API_TOKEN=" $ENV_FILE > old_secrets.txt
grep "^[[:blank:]]*POSTGRES_USER=" $ENV_FILE >> old_secrets.txt
grep "^[[:blank:]]*POSTGRES_PASSWORD=" $ENV_FILE >> old_secrets.txt

cp $BASE_DIR/services/seek/ldh-deployment/docker-compose.env .

tar cvf dags.tar -C $BASE_DIR/services/airflow dags

for v in \
digitaltwins-platform_seek_cache \
digitaltwins-platform_seek_db \
digitaltwins-platform_seek_filestore \
digitaltwins-platform_seek_solr \
digitaltwins-platform_minio_data \
digitaltwins-platform_postgres_data \

do
	echo $v
	docker run --rm \
        -v $DOCKER_VOLS_DIR/$v:/volume \
        -v $(pwd):/backup \
        alpine tar -cvf /backup/${v}.tar -C /volume .
done

cat > README.txt <<EOF
# Data backup of digitaltwins platform taken $now.

# To restore this data backup, copy this directory to the target system, then:
# You can just run this README.txt file if you want

# 0. make sure alpine:latest is loaded in the target docker (docker load -i /mnt/install_src/alpine.tar)

docker compose down
# 2. Edit ~/digitaltwins-platform/.env and adjust SEEK_API_TOKEN according to old_secrets.txt
while IFS='=' read -r key value; do
    sed -i "s|^${key}=.*|${key}=${value}|" ~/digitaltwins-platform/.env
done < old_secrets.txt


cp docker-compose.env ~/digitaltwins-platform/services/seek/ldh-deployment/
#    (note that's going to clobber your existing one)
rm -rf ~/digitaltwins-platform/services/airflow/dags
tar xvf dags.tar -C ~/digitaltwins-platform/services/airflow
~/digitaltwins-platform/buildout/util/delete_vols
~/digitaltwins-platform/buildout/util/new_vols
~/digitaltwins-platform/buildout/util/restore_vols #(while sitting in this directory)

docker compose up -d
EOF

docker compose up -d
