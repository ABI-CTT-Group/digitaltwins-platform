# Improve this, but this is the shell of what needs to happen

# On the system to be copied
docker compose down

sudo su -  << EOF
cd /var/lib/docker/volumes/; tar cvf /tmp/mp.tar digitaltwins*/_data
EOF

docker compose up -d

# copy mp.tar to the backup system, then on that backup system

sudo su - <<EOF
cd /var/lib/docker/volumes/
rm -rf digitaltwins*/_data
tar xvf /tmp/mp.tar
EOF

# Some passwords will then need to be sorted out:
# 1. services/seek/ldh-deployment/docker-compose.env - copy from prod to dev
# 2. services/api/digitaltwins-api/configs.ini - the api token needs to be copied from prod
