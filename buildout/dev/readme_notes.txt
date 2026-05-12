# Tag the MinIO Server
podman tag quay.io/minio/minio localhost/abi-minio:2026-04-09

# Tag the MinIO Client
podman tag docker.io/minio/mc localhost/abi-mc:2026-04-09


podman save -o my_app_cache.tar $(podman compose ps -q | xargs podman inspect --format '{{.ImageName}}')

podman load -i my_app_cache.tar


curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

docker run --rm alpine wget -q --spider http://deb.debian.org && echo "SUCCESS"

sudo usermod -aG docker $USER
newgrp docker


Check this stuff:

./services/airflow/config/airflow.cfg
    Add these two:
    base_url = https://test.digitaltwins.auckland.ac.nz/airflow
    enable_proxy_fix = True

./services/seek/ldh-deployment/docker-compose.env
    Copy the source version when you pull the seek/data across

./services/portal/DigitalTWINS-Portal/docker-compose.yml
    
./.env


- put "127.0.0.1 test.digitaltwins.auckland.ac.nz" into your local /etc/hosts file
- connect to UoA VPN
- Add this entry to your ~/.ssh/config for challengeless connection to "abi_portal"
(your id_ed25519.pub must be in the authorized_keys of ubuntu on the remote machine)

Host abi_portal
    HostName 130.216.216.243
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR

- Run this port forwarding command
    sudo ssh -L 443:localhost:443 -J mpes457@bioeng100.bioeng.auckland.ac.nz abi_portal

The first challenge is for sudo
The second challenge is for the gateway (bioeng100)
You shouldn't be challenged from the abi_portal machine if the ~/.ssh/config is set up correctly.

Now you can open a browser to https://test.digitaltwins.auckland.ac.nz, which you have
told your local machine is actually your local machine. Your port 443 is forwarded
via the gateway "jump machine" (bioeng100) to the remote abi_portal VM.



For your records, after pulling/rebuilding the SEEK/LDH container you need to
recompile assets inside the running container because the image bakes them in
without RAILS_RELATIVE_URL_ROOT set:

# After seek container is up and healthy:
docker exec seek bundle exec rake assets:precompile
docker exec seek bundle exec rake tmp:clear

# Then restart everything to re-resolve DNS
docker compose restart seek workers portal-frontend

This needs to be done any time you:

- First deploy on a new VM
- Pull a new LDH image version
- Change RAILS_RELATIVE_URL_ROOT



===========
Regarding the performance problems of the GUI displaying assays, an AI helper says:

Found the problem — it's not auth, it's a classic N+1 sequential request pattern. When the dashboard loads a study's assays, it:

Fetches the study to get a list of assay IDs
Then loops through each assay ID making a separate HTTP call: await client.get(f"/assays/{obj_id}")
Each of those calls hits digitaltwins-api, which then calls SEEK for the assay, then makes another SEEK call per SOP
With even a handful of assays, that's dozens of sequential network round trips: portal → API → SEEK → API → SEEK → API...

The calls in the loop are awaited one at a time (lines 138-149), so they're sequential despite being async. The fix would be to parallelise them with asyncio.gather() — instead of fetching each assay one by one, fire all the requests simultaneously.

That said, this is a more involved code change and would need to be communicated to the developers. It's a structural issue in dashboard.py rather than a configuration problem. For now at least you know why it's slow.
===========


With any code changes, you may need to do this to get them to stick:
docker compose up -d --build




====================

I have resurrected this system. I fear there are bizarre cached or compiled things in the docker compose system that I don't yet understand. I wonder what I need to do to ensure that the stuff I have running currently is what I would see if I were to drop the VM and start over with the same code set. I'm looking for a faster way to test that my code is stable than dropping and rebuilding the entire VM. Ideally I wouldn't have to download all the images involved into docker again too - yet another thing that makes me lose sleep: Who knows if what gets downloaded today is the same thing that would be used tomorrow?



These are legitimate concerns and they point to a few distinct problems. Let me separate them:

1. "Is what's running what the code says?"
The danger areas in Docker Compose are:

Built images — if you changed a file but didn't rebuild, the old image is still running. Always use:

docker compose up -d --build

not just up -d. The --build forces a rebuild of any service with a build: directive.

Named volumes — these persist across down/up and can contain stale database state, compiled assets, config files. Your platform has several:

docker volume ls | grep digitaltwins

The dangerous ones for you are airflow_postgres-db-volume (Airflow config/connections baked in) and keycloak_data (realm config). A docker compose down does not remove these — you need docker compose down -v to nuke them too.

The "fresh start" test without re-downloading images:

docker compose down -v           # stops everything, removes volumes
docker compose up -d --build     # rebuilds local images, reuses pulled images from cache

This is equivalent to a VM wipe for application state, without re-pulling apache/airflow:3.0.6 etc. Docker keeps pulled images in its local cache indefinitely until you explicitly docker image prune.

2. "Will the same image be downloaded tomorrow?"
No — tags like airflow:3.0.6 are mutable. The registry can push a new image to that tag at any time. The fix is to pin by digest:

# Find the current digest of a running image
docker inspect airflow-apiserver --format '{{.Image}}'

That gives you something like sha256:abc123.... You can then pin in docker-compose:

image: apache/airflow@sha256:abc123...

That digest is immutable — it will always pull the exact same bytes.

3. Practical audit — "is what's running what the files say?"
Run this to see the actual image digest vs what compose thinks it should be:

docker compose ps -q | xargs docker inspect --format '{{.Name}} {{.Config.Image}} {{.Image}}' 

And to check if any container is running a stale build (i.e. image was rebuilt but container wasn't restarted):

docker compose ps

Any service showing Restarting or with an age much older than others after a --build is suspect.

The short answer for your situation
Your fastest "clean slate without re-downloading" is:

docker compose down -v && docker compose up -d --build

Run that from your root digitaltwins-platform directory and it will give you exactly what a fresh VM would give — minus the image downloads, which are safe to reuse from cache since you're not changing the image: references.

The keycloak issue yesterday was almost certainly stale volume state (keycloak_data) conflicting with the new config — the -v flag would have cleared that.

====================


OK, So let's assume I have this fully functioning docker compose system running the way I want it. Now I want to build the exact same system, but inside an airgapped system that doesn't allow me to, for example, go out to the Internet. So downloading and installing docker from get.docker.com, or pulling images is out of the question. Apart from a full image snapshot of the VM, is there a way I can do this?



Yes, there's a well-established approach for this. The key insight is that Docker images are just tar files — you can snapshot and transport them completely independently of any registry.

The Strategy: Save/Load
Step 1 — On your internet-connected VM, capture everything
# Make sure all images are pulled and all custom images are built
docker compose pull
docker compose build

# Get the full list of images your stack uses
docker compose config --images

# Save them all to a single archive
docker save $(docker compose config --images | tr '\n' ' ') \
  | gzip > digitaltwins-images.tar.gz

That .tar.gz is your complete, reproducible image snapshot. The bytes are frozen — this is also the answer to your "will it be the same tomorrow" concern. The tar file is the immutable artefact, not the registry tag.


Step 2 — Transfer to air-gapped machine
Copy over:

digitaltwins-images.tar.gz
Your entire digitaltwins-platform/ directory (code, configs, .env)
Docker offline installer (see below)
Step 3 — On the air-gapped machine
# Load all images in one shot
gunzip -c digitaltwins-images.tar.gz | docker load

# Verify they're all present
docker images

# Then just run normally — no pulls needed
docker compose up -d

Because all images already exist locally, docker compose up won't attempt to reach the internet.

Installing Docker Offline
Docker publishes static binaries that need no apt/yum:

# Download this on the connected machine (pick your arch)
# https://download.docker.com/linux/static/stable/x86_64/
wget https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz

# On the air-gapped machine:
tar xzf docker-27.5.1.tgz
sudo mv docker/* /usr/local/bin/

# Set up the daemon
sudo dockerd &   # or set up as a systemd service

Or if the air-gapped machine already has Docker installed (common in enterprise), skip this entirely.

For Build-Time Dependencies (pip, npm, apt)
If any of your services use build: in the compose file and install packages at build time — those packages are already baked into the image layer when you ran docker compose build. The docker save captures those layers. Nothing gets re-downloaded on the air-gapped machine.

Making This a Habit
Pin images by digest in your compose files (as mentioned earlier), then your save script always captures exactly the right bytes:

# Get digest of a running image for pinning
docker inspect seek --format '{{.Image}}'
# → sha256:abc123...

Then in docker-compose.yml:

image: fairdom/seek@sha256:abc123...

Now your git repo + digitaltwins-images.tar.gz is a fully reproducible, air-gappable deployment unit. You can verify it at any time with docker compose down -v && gunzip -c digitaltwins-images.tar.gz | docker load && docker compose up -d.

============================


wget https://download.docker.com/linux/static/stable/x86_64/docker-29.4.0.tgz
wget https://github.com/docker/compose/releases/download/v5.1.2/docker-compose-linux-x86_64


# on connected machine get and install the pip stuff (or just use apt if you like):
apt-get download python3-pip python3-venv python3.12-venv
sudo dpkg -i python3*.deb

# then download the ansible package for transfer to the airgapped machine:
pip3 download ansible -d ./ansible-packages/
tar czf ansible-packages.tar.gz ansible-packages/


Copy the resulting *.deb and ansible-packages.tar.gz to /mnt/install_src

# on the airgapped machine
# install pip stuff
sudo dpkg -i python3*.deb

# install ansible
tar xzf ansible-packages.tar.gz
pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages

ansible-playbook -i "localhost," -c local airgap_build_step1.yml -e "ansible_user=$USER"
ansible-playbook -i "localhost," -c local airgap_build_step2.yml -e "ansible_user=$USER"
ansible-playbook -i "localhost," -c local airgap_build_step3.yml -e "ansible_user=$USER"


To logout out of grafana/keycloak, if you've logged in but don't have an allowed group:
https://test.digitaltwins.auckland.ac.nz/auth/realms/digitaltwins/protocol/openid-connect/logout?client_id=grafana&post_logout_redirect_uri=https%3A%2F%2Ftest.digitaltwins.auckland.ac.nz%2Fgrafana%2Flogin


These files are important for getting grafana airgapped and proxied and keycloaked:
./services/keycloak/docker-compose.yml
./services/portal/DigitalTWINS-Portal/frontend/nginx.conf
./buildout/dev/fetch_airgap_images.sh
./buildout/dev/trust_ca
./buildout/dev/helm_mod
./buildout/dev/observability/grafana-values.yaml
./buildout/dev/install_observability_airgap.yaml
./buildout/dev/traefik_to_grafana.yml
./buildout/dev/fetch_airgap.sh


SSL cert:
Apr 22 2026 - I quit the idea of having a signing CA and am going back to zerossl for a cert.
The portal VM is Internet facing and attached to the IP address in the DNS for
test.digitaltwins.auckland.ac.nz
so should just work.
sudo snap install --classic certbot
mkdir ~/certs
copy in the renew_cert script (in util) to ~/certs
key your EAB_KID and EAB_HMAC_KEY into ~/keys/eab_kid.key and eab_hmac_key.key
This will create fullchain.pem and privkey.pem
Run your ~/certs/renew_cert
If you look at the portal/docker-compose.yml file, you'll see these need to be moved:
cp fullchain.pem ~/digitaltwins-platform/services/portal/DigitalTWINS-Portal/certs/test.digitaltwins.auckland.ac.nz.crt
cp privkey.pem   ~/digitaltwins-platform/services/portal/DigitalTWINS-Portal/certs/test.digitaltwins.auckland.ac.nz.key
docker compose down
docker compose up -d
In 3 months, you'll need to do it again.
