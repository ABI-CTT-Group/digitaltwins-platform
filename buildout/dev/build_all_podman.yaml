- name: VM setup
  gather_facts: false
#  hosts: portal drai_mp drai_cc
  hosts: portal drai_mp
  environment:
    COMPOSE_PULL: "never"

  tasks:
#########################
# Make sure required env variables are set
  - name: Verify SEEK_ADMIN_PASSWORD environment variable is set
    ansible.builtin.fail:
      msg: "FATAL: The required environment variable SEEK_ADMIN_PASSWORD must be set to run this playbook."
    when: lookup('env', 'SEEK_ADMIN_PASSWORD') | length == 0
#########################

  - name: Generate ED25519 SSH Keypair for application user
    community.crypto.openssh_keypair:
      path: .ssh/id_ed25519
      type: ed25519
      size: 256  # Mandatory for ed25519, though 256 is the default
      force: no  # Do not overwrite if the key already exists
      mode: '0600'

  - name: Fetch the remote public key file
    ansible.builtin.fetch:
      src: .ssh/id_ed25519.pub
      dest: "/tmp/fetched_keys_{{ inventory_hostname }}.pub"
      flat: yes
      fail_on_missing: yes

  - name: Add fetched public keys to localhost authorized_keys
    ansible.posix.authorized_key:
      user: "ubuntu"
      state: present
      # Use the 'item' variable (the host name) in the lookup path
      key: "{{ lookup('file', '/tmp/fetched_keys_{{ item }}.pub') }}"
      comment: '{{ item }} - remote access key'
    delegate_to: localhost
    # Loop over all hosts that were active in the current play
    loop: "{{ play_hosts }}"
    # Ensure the loop only runs once on the control machine, 
    # but processes all keys sequentially.
    run_once: true

  - name: Add 'gendev' SSH configuration block using blockinfile
    ansible.builtin.blockinfile:
      path: .ssh/config
      block: |
        Host gendev
            User ubuntu
            Hostname 163.7.144.201
            StrictHostKeyChecking no
            UserKnownHostsFile /dev/null
            LogLevel ERROR
      marker: "# {mark} ANSIBLE MANAGED BLOCK for gendev"
      create: true
      state: present
      mode: '0644'


###

  - name: Mount existing volume /dev/vdb to /mnt/docker_cache
    become: true
    block:
      - name: Ensure mount directory exists
        ansible.builtin.file:
          path: /mnt/docker_cache
          state: directory
          mode: '0755'
          owner: "1001"  # Set this to your Podman user's UID
          group: "1001"
  
      - name: Mount /dev/vdb and update fstab
        ansible.posix.mount:
          path: /mnt/docker_cache
          src: /dev/vdb
          fstype: auto    # Tells mount to detect the existing ext4/xfs automatically
          opts: defaults
          state: mounted  # This both mounts it NOW and adds it to /etc/fstab
  
  
  # Firewall Security (UFW)
  - name: Allow Standard Web and SSH traffic
    become: true
    community.general.ufw:
      rule: allow
      port: "{{ item }}"
      proto: tcp
    loop: ['22', '80', '443']

  - name: Enable Firewall
    become: true
    community.general.ufw:
      state: enabled
      policy: deny

  - name: install required software
    become: true
    ansible.builtin.package:
      name:
        - "{{ item }}"
      state: present
      update_cache: yes
      cache_valid_time: 3600
    loop:
      - jq
      - curl
      - telnet
      - firewalld
      - net-tools
      - openssl
      - units
      - bc
      - zip
      - postgresql-client
      - certbot
      - podman-docker

  - name: Install modern Docker Compose V2 binary for Podman
    become: true
    get_url:
      url: "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64"
      dest: /usr/bin/docker-compose
      mode: '0755'
      force: yes  # Ensures it overwrites the old v1.29 binary

  - name: Enable Podman socket for the user # Not run as root
    ansible.builtin.systemd:
      name: podman.socket
      state: started
      enabled: yes
      scope: user  # Critical: manages the socket for UID 1001, not root

  - name: Create certs directory
    ansible.builtin.file:
      path: "./digitaltwins-platform/services/portal/DigitalTWINS-Portal/certs"
      state: directory
      mode: '0755'

  - name: Copy crt
    ansible.builtin.copy:
      src: ../util/test.digitaltwins.auckland.ac.nz.crt
      dest: ./digitaltwins-platform/services/portal/DigitalTWINS-Portal/certs
      mode: '0600'

  - name: Copy key
    ansible.builtin.copy:
      src: ../util/test.digitaltwins.auckland.ac.nz.key
      dest: ./digitaltwins-platform/services/portal/DigitalTWINS-Portal/certs
      mode: '0600'

  - name: Set DOCKER_HOST environment variable for the user
    ansible.builtin.lineinfile:
      path: "~/.bashrc"
      line: "export DOCKER_HOST=unix:///run/user/{{ ansible_user_uid }}/podman/podman.sock"
      state: present

  - name: Allow non-root users to bind to ports 80 and 443
    become: true
    ansible.posix.sysctl:
      name: net.ipv4.ip_unprivileged_port_start
      value: '80'
      state: present
      reload: yes

  - name: Allow Podman to run after logout (Linger)
    become: true
    ansible.builtin.command:
      cmd: "loginctl enable-linger {{ ansible_user }}"
      creates: "/var/lib/systemd/linger/{{ ansible_user }}"


  - name: Set up Port Forwarding for 80 and 443
    become: true
    ansible.builtin.iptables:
      table: nat
      chain: PREROUTING
      protocol: tcp
      destination_port: "{{ item.external }}"
      jump: REDIRECT
      to_ports: "{{ item.internal }}"
      comment: "Cloud Port Forwarding"
    loop:
      - { external: 80, internal: 8080 }
      - { external: 443, internal: 8443 }
  
  - name: Open High Ports in Firewall
    become: true
    community.general.ufw:
      rule: allow
      port: "{{ item }}"
      proto: tcp
    loop:
      - '8080'
      - '8443'

  - name: user access
    authorized_key:
      user: "{{ ansible_user }}"
      state: present
      key: "{{ lookup('file', item) }}"
    with_fileglob:
      - "public_keys/*.pub"

  - name: Ensure the keys directory is present
    ansible.builtin.file:
      path: keys
      state: directory
      mode: '0700'

  - name: Load cached Docker images into local daemon
    ansible.builtin.command: podman load -i /mnt/docker_cache/airgap_bundle_20260324.tar
    register: docker_load_output
    changed_when: "'Loaded image' in docker_load_output.stdout"

# Because git pulling has basically stopped functioning in the last couple days...
  - name: Sync code to VM
    ansible.posix.synchronize:
      src: /home/ubuntu/twins/clean_src/digitaltwins-platform/
      dest: /home/ubuntu/digitaltwins-platform/
      archive: yes
      delete: yes
      rsync_opts:
        - '--filter=":- .gitignore"'
        - '--exclude=.git/'

#  - name: Read git checkout platform
#    ansible.builtin.git:
#      repo: https://github.com/ABI-CTT-Group/digitaltwins-platform.git
#      dest: ./digitaltwins-platform
#      depth: 1
#      force: yes
#      recursive: yes  # submodules
#      version: buildout
#
#  - name: update submodules
#    ansible.builtin.command: git submodule update --remote --recursive --depth 1
#    args:
#      chdir: ./digitaltwins-platform


#  - name: Raw git clone (Using a full login shell)
#    ansible.builtin.shell: >
#      bash -lc 'git clone --quiet --depth 1 
#      --branch buildout 
#      --recurse-submodules 
#      --shallow-submodules 
#      https://github.com/ABI-CTT-Group/digitaltwins-platform.git 
#      ./digitaltwins-platform'
#    args:
#      creates: ./digitaltwins-platform
#      executable: /bin/bash
#
#  - name: Raw git clone (bypassing Ansible's stubborn git module)
#    ansible.builtin.command: >
#      git clone --quiet --depth 1
#      --branch buildout 
#      --recurse-submodules 
#      --shallow-submodules 
#      https://github.com/ABI-CTT-Group/digitaltwins-platform.git 
#      ./digitaltwins-platform
#    args:
#      creates: ./digitaltwins-platform
#


#  - name: Read git checkout buildout
#    ansible.builtin.git:
#      #repo: gendev:git/twins_buildout.git
#      repo: https://github.com/ABI-CTT-Group/digitaltwins-platform.git
#      dest: ./twins_buildout
#      force: yes
#      version: buildout
#
  # I don't understand why I need this next step, but it doesn't seem to get the host's DNS setup here
  # and hangs/times out when attempting to pull containers
#  - name: Write docker daemon config for DNS
#    become: yes
#    ansible.builtin.copy:
#      dest: /etc/docker/daemon.json
#      content: |
#        {
#          "dns": ["8.8.8.8", "8.8.4.4"]
#        }
#      mode: '0644'
#

#  - name: Restart Docker
#    become: yes
#    ansible.builtin.systemd:
#      name: docker
#      state: restarted

  - name: check for .env
    stat:
      path: "./digitaltwins-platform/.env"
    register: file_check1

  - name: Copy .env
    ansible.builtin.copy:
      src: ../data/.env
      dest: ./digitaltwins-platform/.env
      mode: '0600'

#  - name: .env
#    ansible.builtin.command: cp .env.template .env
#    args:
#      chdir: ./digitaltwins-platform
#    when: not file_check1.stat.exists

#  - name: airflow_uid
#    shell: |
#      MYIP=$(curl ifconfig.me)
#      sed -i "s/PORTAL_BACKEND_HOST_IP=.*/PORTAL_BACKEND_HOST_IP=$MYIP/g" .env
#    args:
#      chdir: ./digitaltwins-platform

#  - name: airflow_uid
#    shell: |
#      MYUID=$(id -u)
#      sed -i "s/AIRFLOW_UID=.*/AIRFLOW_UID=$MYUID/g" .env
#    args:
#      chdir: ./digitaltwins-platform

#  - name: check for api .configs.ini
#    stat:
#      path: "./digitaltwins-platform/services/api/digitaltwins-api/configs.ini"
#    register: file_check2

#  - name: api configs.ini
#    ansible.builtin.command: cp ./services/api/digitaltwins-api/configs.ini.template ./services/api/digitaltwins-api/configs.ini
#    args:
#      chdir: ./digitaltwins-platform
#    when: not file_check2.stat.exists

  - name: check for file
    stat:
      path: "./digitaltwins-platform/services/seek/ldh-deployment/docker-compose.env"
    register: file_check3

  - name: seek database password setup
    shell: |
      cat ./services/seek/ldh-deployment/docker-compose.env.tpl | sed "s|<db-password>|$(openssl rand -base64 21)|" | sed "s|<root-password>|$(openssl rand -base64 21)|" > ./services/seek/ldh-deployment/docker-compose.env
    args:
      chdir: ./digitaltwins-platform
    when: not file_check3.stat.exists

#  - name: Set kc_client_secret from environment variable
#    ansible.builtin.set_fact:
#      kc_client_secret: "{{ lookup('env', 'KC_CLIENT_SECRET') }}"
#
#  - name: Ensure KEYCLOAK_CLIENT_SECRET is set in .env
#    ansible.builtin.lineinfile:
#      path: ./digitaltwins-platform/.env
#      regexp: '^KEYCLOAK_CLIENT_SECRET='
#      line: KEYCLOAK_CLIENT_SECRET={{ kc_client_secret }}
#      create: true
#      mode: '0600'  # Restrict permissions since it contains a secret

#  - name: Set kc_bookstrap_admin_password from environment variable
#    ansible.builtin.set_fact:
#      kc_bootstrap_admin_password: "{{ lookup('env', 'KC_BOOTSTRAP_ADMIN_PASSWORD') }}"
#
#  - name: Ensure KC_BOOTSTRAP_ADMIN_PASSWORD is set in .env
#    ansible.builtin.lineinfile:
#      path: ./digitaltwins-platform/.env
#      regexp: '^KC_BOOTSTRAP_ADMIN_PASSWORD='
#      line: KC_BOOTSTRAP_ADMIN_PASSWORD="{{ kc_bootstrap_admin_password }}"
#      create: true
#      mode: '0600'  # Restrict permissions since it contains a secret

#  - name: Ensure api_token is dummy for the moment in .env
#    ansible.builtin.lineinfile:
#      path: ./digitaltwins-platform/.env
#      regexp: '^SEEK_API_TOKEN='
#      line: SEEK_API_TOKEN=dummy
#      create: true
#      mode: '0600'  # Restrict permissions since it contains a secret

  - name: volume create
    shell: |
        . ./.env && podman volume create ${COMPOSE_PROJECT_NAME}_filestore && podman volume create ${COMPOSE_PROJECT_NAME}_db
    args:
      chdir: ./digitaltwins-platform

  - name: Initialize airflow.cfg
    ansible.builtin.command: podman compose run airflow-cli airflow config list
    args:
      chdir: ./digitaltwins-platform

  - name: allow_headers
    shell: |
      sed -i "s/^access_control_allow_headers.*$/access_control_allow_headers = origin, content-type, accept/" ./services/airflow/config/airflow.cfg
    args:
      chdir: ./digitaltwins-platform

  - name: allow_methods
    shell: |
      sed -i "s/^access_control_allow_methods.*/access_control_allow_methods = POST, GET, OPTIONS, DELETE/" ./services/airflow/config/airflow.cfg
    args:
      chdir: ./digitaltwins-platform

  - name: allow_origins
    shell: |
      sed -i "s/^access_control_allow_origins.*/access_control_allow_origins = /" ./services/airflow/config/airflow.cfg
    args:
      chdir: ./digitaltwins-platform

#  - name: Set FACT from environment variable
#    ansible.builtin.set_fact:
#      kc_https_key_store_password: "{{ lookup('env', 'KC_HTTPS_KEY_STORE_PASSWORD') }}"
#
#  - name: keystore password 1
#    shell: |
#      sed -i "s/KC_HTTPS_KEY_STORE_PASSWORD=.*/KC_HTTPS_KEY_STORE_PASSWORD=\"{{ kc_https_key_store_password }}\"/g" .env
#    args:
#      chdir: ./digitaltwins-platform
#
#  - name: keystore password 2
#    shell: |
#      sed -i "s/#KC_HTTPS_KEY_STORE_PASSWORD=/KC_HTTPS_KEY_STORE_PASSWORD=/g" .env
#    args:
#      chdir: ./digitaltwins-platform

#  - name: keystore password
#    shell: |
#      sed -i "s/CLIENT_SECRET=.*/CLIENT_SECRET=\"{{ kc_client_secret }}\"/g" .env
#    args:
#      chdir: ./digitaltwins-platform

  - name: airflow-init
    ansible.builtin.command: podman compose up airflow-init
    args:
      chdir: ./digitaltwins-platform

  - name: docker down
    ansible.builtin.command: podman compose down
    args:
      chdir: ./digitaltwins-platform

###

  - name: Copy production configuration file to remote server
    ansible.builtin.copy:
      src: server.jks
      dest: ./digitaltwins-platform/services/keycloak/server.jks
      mode: '0644'

  - name: Copy production configuration file to remote server
    ansible.builtin.copy:
#      src: ../data/digitaltwins_realm_202603051056.json
      src: ../data/realm-cc-digitaltwins_20260322.json
      dest: ./digitaltwins-platform/services/keycloak/import/digitaltwins-realm.json
      mode: '0644'

########

  - name: Startup seek
#    ansible.builtin.command: docker compose -f services/seek/ldh-deployment/docker-compose.yml --env-file ./.env up -d
    ansible.builtin.command: podman compose up -d seek
    args:
      chdir: ./digitaltwins-platform

#  - name: Sleep on the remote host for a bit
#    ansible.builtin.shell: sleep 60
#    changed_when: true # Ensures the task reports 'changed' every time it runs
#

# Better solution to the "wait" problem...

  - name: Wait for background migrations to create the users table
    ansible.builtin.command: >
      podman exec digitaltwins-platform-seek-1 bash -c 
      'cd /seek && RAILS_ENV=production bundle exec rails runner "exit(ActiveRecord::Base.connection.table_exists?(:users) ? 0 : 1)"'
    register: table_check
    # Try up to 15 times, waiting 10 seconds between attempts (max 150 seconds)
    retries: 15
    delay: 10
    # Keep looping until the command returns an exit code of 0 (Success)
    until: table_check.rc == 0
    # This prevents Ansible from reporting 'changed' since we are only reading state, not modifying it
    changed_when: false

  - name: Set SEEK_ADMIN_PASSWORD from environment variable
    ansible.builtin.set_fact:
      seek_admin_password: "{{ lookup('env', 'SEEK_ADMIN_PASSWORD') }}"

  - name: admin user
    ansible.builtin.command: "./create-admin-user.sh admin {{ seek_admin_password }} matt.pestle@auckland.ac.nz"
    args:
      chdir: ./digitaltwins-platform/buildout/util

  - name: features 
    ansible.builtin.command: "./enable-features.sh"
    args:
      chdir: ./digitaltwins-platform/buildout/util

  - name: token 
    ansible.builtin.command: "./generate-token.sh"
    args:
      chdir: ./digitaltwins-platform/buildout/util

  - name: all down
    ansible.builtin.command: podman compose down
    args:
      chdir: ./digitaltwins-platform

  - name: Start docker compose services
    shell: |
      podman compose up -d
    args:
      chdir: ./digitaltwins-platform


  - name: Create a bulletproof systemd service for the twins stack
    ansible.builtin.copy:
      dest: "~/.config/systemd/user/twins.service"
      content: |
        [Unit]
        Description=Digital Twins Platform Stack
        After=network-online.target
  
        [Service]
        Type=simple
        # Point to your project folder
        WorkingDirectory=/home/{{ ansible_user }}/digitaltwins-platform
        # The exact command to start your stack
        ExecStart=/usr/bin/podman compose up
        # The command to stop it cleanly
        ExecStop=/usr/bin/podman compose down
        Restart=always
  
        [Install]
        WantedBy=default.target
      mode: '0644'
  
  - name: Force systemd to see the new service
    ansible.builtin.systemd:
      daemon_reload: yes
      scope: user
  
  - name: Start and Enable the service
    ansible.builtin.systemd:
      name: twins
      state: started
      enabled: yes
      scope: user
  

  - name: Ensure COMPOSE_FILE is in .bash_aliases
    ansible.builtin.lineinfile:
      path: ./.bash_aliases
      regexp: '^export COMPOSE_FILE='
      line: "export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml"
      create: true
      mode: '0600'  # Restrict permissions since it contains a secret
