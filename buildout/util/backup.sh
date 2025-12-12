# Backup the docker volumes
# matt.pestle@auckland.ac.nz
# Dec 2025
#
# These just get tar-ed to a local file in ~/backups.
# Log goes into ~/logs.
#
# See the stuff below the last "exit" command
# for instructions on how to restore elsewhere.

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
docker compose down

sudo su -  << EOF
cd /var/lib/docker/volumes/; tar cvf $BACKUP_FILE digitaltwins*/_data
EOF

if [ $? -ne 0 ]; then
  echo "Archive command failed."
  docker compose up -d &
  exit 1
fi

docker compose up -d &

exit


# After a backup, you may wish to restore it elsewhere, to, say, $TGT_VM
# where you have already installed the system (ie., you've run build_all.yaml)
# Here's a template.

SRC_VM=abi_portal
TGT_VM=abi_mp

BACKUP_FILE=docker_vols_20251212131901.tar.gz

scp $SRC_VM:backups/$BACKUP_FILE $TGT_VM:/tmp/

# Then go onto the $TGT_VM and
cd digitaltwins-platform
docker compose down

sudo su - <<EOF
cd /var/lib/docker/volumes/
rm -rf digitaltwins*/_data
tar xvf /tmp/$BACKUP_FILE
EOF

#
# Finally, some manual things will then need to be sorted out:
# 1. services/seek/ldh-deployment/docker-compose.env - copy from prod to dev
# 2. services/api/digitaltwins-api/configs.ini - the api token needs to be copied from prod
# 3. the site base host of seek needs to be updated to reflect new environment
#
# These can be accomplished with the following steps:

# 1.
scp $SRC_VM:digitaltwins-platform/services/seek/ldh-deployment/docker-compose.env \
    $TGT_VM:digitaltwins-platform/services/seek/ldh-deployment/docker-compose.env

# 2.
API_TOKEN=$(ssh $SRC_VM "grep api_token digitaltwins-platform/services/api/digitaltwins-api/configs.ini" | \
    awk -F= '{print $2}' | tr -d \"
)
#echo $API_TOKEN
ssh $TGT_VM sed -i "s/api_token=.*/api_token=\"$API_TOKEN\"/" \
    digitaltwins-platform/services/api/digitaltwins-api/configs.ini

# 3.
ssh $TGT_VM digitaltwins-platform/buildout/util/swap_seek_ip.sh
