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

# sudo tar --xattrs --acls --numeric-owner -xzvf $BACKUP_FILE -C /var/lib/docker/volumes/

sudo su -  << EOF
cd /var/lib/docker/volumes; tar --xattrs --acls -czvf $BACKUP_FILE --exclude='digitaltwins-platform_cache' -C /var/lib/docker/volumes/ digitaltwins*
EOF

if [ $? -ne 0 ]; then
  echo "Archive command failed."
  docker compose up -d &
  exit 1
fi

docker compose up -d &

exit
