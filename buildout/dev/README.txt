This directory contains everything required to run up the digitaltwins platform
on an airgapped Ubuntu 24.04 machine with no connection to the Internet.

The steps will be
- Elsewhere,
     (these steps are done for the domain test.digitaltwins.auckland.ac.nz)
     - create the CA used to sign the cert
     - create and sign the cert to be used by the website

- Figure out what IP address you are going to use for this domain

- Put that IP address in your local /etc/hosts file as test.digitaltwins.auckland.ac.nz
     (or set up your DNS entry to point that domain to your IP)

- Get the install source mounted somehow (airgap_build_step0.yml, or equivalent - see below)
  If the source directory is attached to your VM as a volume on /dev/vdb, for example, as root:
      mkdir -p /mnt/install_src
      chmod 0755 /mnt/install_src
      chown ubuntu:ubuntu /mnt/install_src
      mount -o defaults /dev/vdb /mnt/install_src
      echo "/dev/vdb /mnt/install_src auto defaults 0 0" >> /etc/fstab

- Install the packages required to run ansible (python pip)
     sudo dpkg -i python3*.deb

- Install ansible
     cd ~
     tar xzf /mnt/install_src/ansible-packages.tar.gz
     pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages

# Get $HOME/.local/bin (where ansible is) onto your $PATH
     PATH=$PATH:~/.local/bin/
  (probably want to put that into your .bashrc or equivalent)

- Copy the airgap_build_step*.yml files to $HOME and move to that directory

- Run
      ansible-playbook -i "localhost," -c local airgap_build_step1.yml \
		-e "ansible_user=$USER" \
		-e "install_src_dir=/mnt/install_src"
  To set up the firewall to airgap the machine

- Run
      ansible-playbook -i "localhost," -c local airgap_build_step2.yml \
		-e "ansible_user=$USER" \
		-e "install_src_dir=/mnt/install_src"
  To install docker and docker compose and set them up as a server to survive reboots

- Log out and back in again so you get a new session and can control docker

- Set three environment variables with your chosen "secrets"
      export SEEK_ADMIN_PASSWORD=<seek_admin_password>
      export MYSQL_ROOT_PASSWORD=<mysql_root_password>
      export MYSQL_PASSWORD=<mysql_password>

- Run
      ansible-playbook -i "localhost," -c local airgap_build_step3.yml \
		-e "ansible_user=$USER" \
		-e "install_src_dir=/mnt/install_src"
  To install and start then digitaltwins platform

- export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml

- docker compose down

- Set these parameters in ~/digitaltwins-platform/services/airflow/config/airflow.cfg :
    base_url = https://test.digitaltwins.auckland.ac.nz/airflow
    enable_proxy_fix = True
  These are required to get the /airflow proxy functioning correctly.

- docker compose up -d

- Now you should be able to open your browser to
	https://test.digitaltwins.auckland.ac.nz         (for portal)
	https://test.digitaltwins.auckland.ac.nz/seek    (for seek - admin password integrated in build)
	https://test.digitaltwins.auckland.ac.nz/jupyter (for jupyterlab - single user still, with token)
	https://test.digitaltwins.auckland.ac.nz/auth    (for keycloak management)
	https://test.digitaltwins.auckland.ac.nz/airflow (for airflow management - auth still baked in to installation)



The docker images in this bundle have been built to proxy the seek system at
	/seek
which involves setting the env variable
	RAILS_RELATIVE_URL_ROOT=/seek
After pulling/rebuilding the SEEK/LDH container you need to
recompile assets inside the running container because the image bakes them in
without RAILS_RELATIVE_URL_ROOT set:
  After seek container is up and healthy:
    docker exec seek bundle exec rake assets:precompile
    docker exec seek bundle exec rake tmp:clear

# Then restart everything to re-resolve DNS
    docker compose restart seek workers portal-frontend
(I don't know if this will work in an airgapped environment)

This needs to be done any time you:

- First deploy on a new VM
- Pull a new LDH image version
- Change RAILS_RELATIVE_URL_ROOT



# Files in the install_src directory:

data/.env - This is the main configuration env file. It needs to be placed into
	~/digitaltwins-platform/
  and possibly adjusted. It contains secrets, so don't put it into a repo.
  You can compare it to .env.template in the repo to see what changed.

airgap_build_step[0-3].yml - ansible playbooks for setup/installation

alpine.tar - required for utils backup_vols and restore_vols, for doing cold backups
and restores of the seek related datafiles to a different system.
Created with (on a connected machine [ie non airgapped, that can get to Internet]):
	docker save alpine:latest > alpine.tar
Then copy alpine.tar to the airgapped environment and run
	docker load -i alpine.tar
You will then be able to run the backup_vols and restore_vols airgapped.


ansible-packages.tar.gz - The bundle of packages required to install ansible.
To create, go to the connected machine where you have things running, and do
	pip3 download ansible -d ./ansible-packages/
	tar czf ansible-packages.tar.gz ansible-packages/
Then, copy ansible-packages.tar.gz to the airgapped machine and run:
	tar xzf /mnt/install_src/ansible-packages.tar.gz
	pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages


clean_src - this is the source code: the digitaltwins-platform repo and its 3 submodules
	along with the changes that I made to get it all up and proxying, etc.
	I will put those into a separate branch.

digitaltwins-images-all.tar.gz - Bundle of all docker images required.
	Built on a non-airgapped build. This uses the command
		docker compose ps -aq
	which lists the actual image used by every container (including exited ones
	like minio-init), regardless of whether it came from build: or image:.
	Use this as your definitive save list instead of docker compose config --images.
	So we do the following:

		docker compose ps -aq | \
		xargs docker inspect --format '{{.Config.Image}}' | \
		sort -u | \
		xargs docker save | \
		gzip > digitaltwins-images-all.tar.gz 


DigitalTwinsKeycloakInternalCA.pem - The public key of the certificate authority, which needs to be imported
	and thus "trusted" in order to browse the site. Created using util/create_root_ca.
	DEPRECATED! Not using this CA business anymore. Got a cert from zerossol.


docker-29.4.0.tgz - the docker bundle required for installation of docker in an airgapped environment.
	Retrieve this file with
		wget https://download.docker.com/linux/static/stable/x86_64/docker-29.4.0.tgz
	It is installed as part of airgap_build_step2.yml

docker-compose-linux-x86_64-v5.1.2 - docker compose executable.
	Retrieve with
		 wget https://github.com/docker/compose/releases/download/v5.1.2/docker-compose-linux-x86_64
	It is installed as part of airgap_build_step2.yml

public_keys - The public ssh keys of users you want to be able to connect to the built-out VM.
	Put into place by tasks in airgap_build_step3.yml

*.deb files - In order to install ansible, we need pip and a few things. One simple way to retrieve is
	to just go to a non-airgapped machine (which can talk to the Internet) and run:
		apt-get download python3-pip python3-venv python3.12-venv
	This will download/create these files:
		python3.12-venv_3.12.3-1ubuntu0.12_amd64.deb
		python3-pip_24.0+dfsg-1ubuntu1.3_all.deb
		python3-venv_3.12.3-0ubuntu2.1_amd64.deb
	Then after you get these into the airgapped environment, you can run
		sudo dpkg -i python3*.deb
	to install them. Then you will have pip, etc. and be able to install/run ansible.

data/digitaltwins-realm.json - The keycloak realm which we will import into keycloak when it comes up.
	See airgap_build_step3.yml, which places this file into the appropriate position on disk
	so that when keycloak starts, if it doesn't already have a digitaltwins realm, it will import this.
	Note particularly the "users: "section, which contains users with plaintext passwords, such as:
		{ 
		  "username": "mp1",
		  "firstName": "mp1",
		  "lastName": "mp1",
		  "email": "mp1@example.com",
		  "emailVerified": false,
		  "enabled": true,
		  "createdTimestamp": 1772560650398,
		  "totp": false,
		  "credentials": [ {
		    "type": "password",
		    "value": "mp1",
		    "temporary": false
		  } ],
		  "disableableCredentialTypes": [ ],
		  "requiredActions": [ ],
		  "realmRoles": [ "default-roles-digitaltwins" ],
		  "notBefore": 0,
		  "groups": [ "/admin", "/clinician", "/researcher" ]
		} 
	I have defined mp1, mp2, and admin users here.

data/test.digitaltwins.auckland.ac.nz.crt and data/test.digitaltwins.auckland.ac.nz.key -
	SSL cert/key used by the portal webserver. Created using getcert on the portal VM
	(which is the machine under the registered IP for test.digitaltwins.auckland.ac.nz)
	airgap_build_step3.yml copies these into
		./digitaltwins-platform/services/portal/DigitalTWINS-Portal/certs
	where they make their way into the nginx system (see the docker-compose.yml mounts).

Logout URL if you need it:
https://test.digitaltwins.auckland.ac.nz/auth/realms/digitaltwins/protocol/openid-connect/logout?client_id=grafana&post_logout_redirect_uri=https%3A%2F%2Ftest.digitaltwins.auckland.ac.nz%2Fgrafana%2Flogin

For observability:

Make sure these two variables are set: (see data/pwords.txt), then

export GRAFANA_ADMIN_PASSWORD=yourpassword
export GRAFANA_OAUTH_SECRET=yoursecret

ansible-playbook -i 'localhost,' -c local \
  -e "ansible_user=$(whoami)" \
  -e "install_src_dir=/mnt/install_src/airgap" \
  /mnt/install_src/install_observability_airgap.yaml

