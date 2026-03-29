- name: VM setup
  gather_facts: false
#  hosts: portal drai_mp drai_cc
  hosts: portal drai_mp
#  environment:
#    DOCKER_HOST: "unix:///run/podman/podman.sock"

#  environment:
#    COMPOSE_PULL: "never"

  tasks:
#########################
# Make sure required env variables are set
  - name: Verify SEEK_ADMIN_PASSWORD environment variable is set
    ansible.builtin.fail:
      msg: "FATAL: The required environment variable SEEK_ADMIN_PASSWORD must be set to run this playbook."
    when: lookup('env', 'SEEK_ADMIN_PASSWORD') | length == 0
#########################

#  - name: Generate ED25519 SSH Keypair for application user
#    community.crypto.openssh_keypair:
#      path: .ssh/id_ed25519
#      type: ed25519
#      size: 256  # Mandatory for ed25519, though 256 is the default
#      force: no  # Do not overwrite if the key already exists
#      mode: '0600'

#  - name: Fetch the remote public key file
#    ansible.builtin.fetch:
#      src: .ssh/id_ed25519.pub
#      dest: "/tmp/fetched_keys_{{ inventory_hostname }}.pub"
#      flat: yes
#      fail_on_missing: yes

#  - name: Add fetched public keys to localhost authorized_keys
#    ansible.posix.authorized_key:
#      user: "{{ ansible_user }}"
#      state: present
#      # Use the 'item' variable (the host name) in the lookup path
#      key: "{{ lookup('file', '/tmp/fetched_keys_{{ item }}.pub') }}"
#      comment: '{{ item }} - remote access key'
#    delegate_to: localhost
#    # Loop over all hosts that were active in the current play
#    loop: "{{ play_hosts }}"
#    # Ensure the loop only runs once on the control machine, 
#    # but processes all keys sequentially.
#    run_once: true

#  - name: Add 'gendev' SSH configuration block using blockinfile
#    ansible.builtin.blockinfile:
#      path: .ssh/config
#      block: |
#        Host gendev
#            User {{ ansible_user }}
#            Hostname 163.7.144.201
#            StrictHostKeyChecking no
#            UserKnownHostsFile /dev/null
#            LogLevel ERROR
#      marker: "# {mark} ANSIBLE MANAGED BLOCK for gendev"
#      create: true
#      state: present
#      mode: '0644'


###

  - name: Ensure mount directory exists
    become: true
    ansible.builtin.file:
      path: /mnt/docker_cache
      state: directory
      mode: '0755'
      owner: "{{ ansible_user }}"
      group: "{{ ansible_user }}"
  
  - name: Mount /dev/vdb and update fstab
    become: true
    ansible.posix.mount:
      path: /mnt/docker_cache
      src: /dev/vdb
      fstype: auto    # Tells mount to detect the existing ext4/xfs automatically
      opts: defaults
      state: mounted  # This both mounts it NOW and adds it to /etc/fstab
  
  - name: Allow Standard Web and SSH traffic
    become: true
    community.general.ufw:
      rule: allow
      port: "{{ item }}"
      proto: tcp
    loop: ['22', '80', '443', '8080', '8443']

  - name: Allow UFW to route redirected traffic
    become: true
    ansible.builtin.lineinfile:
      path: /etc/default/ufw
      regexp: '^DEFAULT_FORWARD_POLICY='
      line: 'DEFAULT_FORWARD_POLICY="ACCEPT"'

  - name: Configure UFW Port Forwarding (80 -> 8080, 443 -> 8443)
    become: true
    ansible.builtin.blockinfile: 
      path: /etc/ufw/before.rules
      insertbefore: BOF 
      marker: "# {mark} ANSIBLE MANAGED PORT FORWARDING"
      block: |
        *nat
        :PREROUTING ACCEPT [0:0]
        -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
        -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 8443
        COMMIT
        # Blank line after COMMIT is safer for UFW parsing

  - name: Enable Firewall and Set Default Deny
    become: true
    community.general.ufw:
      state: enabled
      direction: incoming
      policy: deny

  - name: Reload UFW to ensure everything is fresh
    become: true
    ansible.builtin.command: ufw reload





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
      - podman
      - podman-compose
      - net-tools
      - bc
      - zip
#      - openssl
#      - firewalld
#      - units
#      - postgresql-client
#      - certbot
#      - iptables-persistent





  - name: Ensure external podman volumes exist
    containers.podman.podman_volume:
      name: "{{ item }}"
      state: present
    loop:
      - digitaltwins-platform_filestore
      - digitaltwins-platform_db



#  - name: Enable Lingering for ubuntu user
#    become: true
#    ansible.builtin.command: "loginctl enable-linger {{ ansible_user }}"
#    args:
#      creates: "/var/lib/systemd/linger/{{ ansible_user }}"
 
 
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
      src: /home/{{ ansible_user }}/twins/clean_src/digitaltwins-platform/
      dest: /home/{{ ansible_user }}/digitaltwins-platform/
      archive: yes
      delete: yes
      rsync_opts:
        - '--filter=":- .gitignore"'
        - '--exclude=.git/'

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

  - name: check for .env
    stat:
      path: "./digitaltwins-platform/.env"
    register: file_check1

  - name: Copy .env
    ansible.builtin.copy:
      src: ../data/.env
      dest: ./digitaltwins-platform/.env
      mode: '0600'

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

#podman run --rm -it   -v ./config:/opt/airflow/config:Z   docker.io/apache/airflow:latest   bash -c "airflow config list --defaults > /opt/airflow/config/airflow.cfg"


  - name: Initialize airflow.cfg
    ansible.builtin.command: podman compose run airflow-cli airflow config list
    args:
      chdir: ./digitaltwins-platform

  # The last config list puts a wonky ownership on the .cfg file, which we need to adjust, so ...
  - name: Force ubuntu ownership on Airflow config
    become: true
    ansible.builtin.file:
      path: "/home/{{ ansible_user }}/digitaltwins-platform/services/airflow/config/airflow.cfg"
      owner: "{{ ansible_user }}"
      group: "{{ ansible_user }}"
      mode: '0644'

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

#podman run --rm -it \
#  --name airflow-init-manual \
#  --env-file .env \
#  -v ./dags:/opt/airflow/dags:Z \
#  -v ./logs:/opt/airflow/logs:Z \
#  -v ./plugins:/opt/airflow/plugins:Z \
#  -v ./config:/opt/airflow/config:Z \
#  docker.io/apache/airflow:latest \
#  airflow db migrate


  - name: airflow-init
    ansible.builtin.command: podman compose up airflow-init
    args:
      chdir: ./digitaltwins-platform

# podman stop -a
# podman rm -a
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

#  - name: volume create1
#    shell: |
#        podman volume create digitaltwins-platform_filestore
#    args:
#      chdir: ./digitaltwins-platform
#
#  - name: volume create2
#    shell: |
#        podman volume create digitaltwins-platform_db
#    args:
#      chdir: ./digitaltwins-platform

  - name: Startup seek
    ansible.builtin.command: podman compose up -d seek
    args:
      chdir: ./digitaltwins-platform

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

  - name: Ensure COMPOSE_FILE is in .bash_aliases
    ansible.builtin.lineinfile:
      path: "~/.bashrc"
      regexp: '^export COMPOSE_FILE='
      line: "export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml"
      create: true
      mode: '0600'  # Restrict permissions since it contains a secret

#  - name: Create the Twins service running as ubuntu user
#    become: true
#    ansible.builtin.copy:
#      dest: "/etc/systemd/system/twins.service"
#      content: |
#        [Unit]
#        Description=Digital Twins Platform Stack
#        # We still bind to the system socket, but run the command as ubuntu
#        BindsTo=podman.socket
#        After=network-online.target podman.socket
#        JobTimeoutSec=60
#  
#        [Service]
#        Type=oneshot
#        RemainAfterExit=yes
#        ## CRITICAL: Run as the ubuntu user
#        User={{ ansible_user }}
#        Group={{ ansible_user }}
#        WorkingDirectory=/home/{{ ansible_user }}/digitaltwins-platform
#        
#        # Use the system-wide socket we permissioned with 0666
#        Environment=DOCKER_HOST=unix:///run/podman/podman.sock
#        
#        ExecStart=/usr/bin/podman compose up -d
#        ExecStop=/usr/bin/podman compose down
#  
#        [Install]
#        WantedBy=multi-user.target
#      mode: '0644'

#  - name: Reload systemd and enable the twins service
#    become: true
#    ansible.builtin.systemd:
#      name: twins.service
#      daemon_reload: yes  # This tells systemd to look for the new file
#      enabled: yes        # This ensures it starts on reboot
#      state: started      # This starts it right now  

  - name: Set DOCKER_HOST environment variable for the user
    ansible.builtin.lineinfile:
      path: "~/.bashrc"
      line: "export DOCKER_HOST=unix:///run/podman/podman.sock"
      state: present
