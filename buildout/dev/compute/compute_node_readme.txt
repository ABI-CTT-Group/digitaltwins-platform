This directory contains everything required to run up the digitaltwins platform
compute node on an airgapped Ubuntu 24.04 machine with no connection to the Internet.


The stuff that needs to be in the install source directory (I'm just using ~/compute) for the compute:
docker-compose.yml 
compose_node_readme.txt # this file
digitaltwins-worker.service

# and the following the from main platform's install_src need to be copied into ~/compute:
PLATFORM=abi_mp
TGT=abi_compute2
scp $PLATFORM:/mnt/install_src/airgap_build_step2.yml $TGT:compute/
scp $PLATFORM:/mnt/install_src/airflow-worker.tar.gz $TGT:compute/
scp $PLATFORM:/mnt/install_src/ansible-packages.tar.gz $TGT:compute/
scp $PLATFORM:/mnt/install_src/docker-29.4.0.tgz $TGT:compute/
scp $PLATFORM:/mnt/install_src/docker-compose-linux-x86_64-v5.1.2 $TGT:compute/
scp $PLATFORM:/mnt/install_src/airgap/apt-debs/python3.12-venv_3.12.3-1ubuntu0.12_amd64.deb $TGT:compute/
scp $PLATFORM:/mnt/install_src/airgap/apt-debs/python3-pip_24.0+dfsg-1ubuntu1.3_all.deb $TGT:compute/
scp $PLATFORM:/mnt/install_src/airgap/apt-debs/python3-venv_3.12.3-0ubuntu2.1_amd64.deb $TGT:compute/



- Install the packages required to run ansible (python pip)
     sudo dpkg -i python3*.deb

- Install ansible
     cd ~
     tar xzf ~/compute/ansible-packages.tar.gz
     pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages

# Get $HOME/.local/bin (where ansible is) onto your $PATH
     PATH=$PATH:~/.local/bin/
  (probably want to put that into your .bashrc or equivalent)

- Run
      ansible-playbook -i "localhost," -c local airgap_build_step2.yml \
		-e "ansible_user=$USER" \
		-e "install_src_dir=~/compute"
  To install docker and docker compose and set them up as a server to survive reboots

- Log out and back in again so you get a new session and can control docker

- mkdir digitaltwins-compute

- on the main platform,
  docker save digitaltwins-platform-airflow-worker:latest | gzip > airflow-worker.tar.gz
  and copy that to the compute node

- 

- scp -r the following from main platform ~/digitaltwins-platform/services/airflow
  into digitaltwins-compute/ on the compute node
PLATFORM=abi_mp
TGT=abi_compute2
	scp -r $PLATFORM:digitaltwins-platform/services/airflow/config  $TGT:digitaltwins-compute/
	scp -r $PLATFORM:digitaltwins-platform/services/airflow/dags    $TGT:digitaltwins-compute/
	scp -r $PLATFORM:digitaltwins-platform/services/airflow/data    $TGT:digitaltwins-compute/
	scp -r $PLATFORM:digitaltwins-platform/services/airflow/logs    $TGT:digitaltwins-compute/
	scp -r $PLATFORM:digitaltwins-platform/services/airflow/plugins $TGT:digitaltwins-compute/

- copy in the .env and the docker-compose.yml file to digitaltwins-compute directory
- adjust MAIN_VM_IP and DIGITALTWINS_API_BASE_URL to reflect the platform's IP address

- export COMPOSE_FILE=~/digitaltwins-compute/docker-compose.yml
 (that might go in your .bashrc or equivalent)

- docker load -i airflow-worker.tar.gz 

- docker compose up -d

- docker compose down # when you're ready to bring it down.


sudo systemctl enable docker

cp digitaltwins-worker.service /etc/systemd/system/digitaltwins-worker.service

sudo systemctl daemon-reload
sudo systemctl enable digitaltwins-worker
