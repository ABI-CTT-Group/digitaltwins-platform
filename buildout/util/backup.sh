# Backup the docker volumes
#

export TZ=Pacific/Auckland
LOG_DIR=${LOG_DIR:=~/logs}
BACKUP_DIR=${BACKUP_DIR:=~/backups}

[[ -d $LOG_DIR ]] || {
    mkdir $LOG_DIR || exit 1
}
[[ -d $BACKUP_DIR ]] || {
    mkdir $BACKUP_DIR || exit 1
}
now=$(date +%Y%m%d%H%M%S)

LOG_FILE=$LOG_DIR/backup_$now.log

BACKUP_FILE=${BACKUP_DIR}/docker_vols_${now}.tar.gz

exec > $LOG_FILE 2>&1

date


# On the system to be copied
export COMPOSE_FILE="~/digitaltwins-platform/docker-compose.yml"

docker compose down

sudo su -  << EOF
cd /var/lib/docker/volumes/; tar cvf $BACKUP_FILE digitaltwins*/_data
EOF

if [ $? -ne 0 ]; then
  echo "Archive command failed."
  docker compose up -d
  exit 1
fi

docker compose up -d

#
## copy $BACKUP_FILE to the backup system, then on that backup system
#
#sudo su - <<EOF
#cd /var/lib/docker/volumes/
#rm -rf digitaltwins*/_data
#tar xvf $BACKUP_FILE
#EOF
#
## Some passwords will then need to be sorted out:
## 1. services/seek/ldh-deployment/docker-compose.env - copy from prod to dev
## 2. services/api/digitaltwins-api/configs.ini - the api token needs to be copied from prod
