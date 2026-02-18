How to build out digital twins platform (terraform/ansible)
on an openstack cloud platform (here we use nectar). Includes
an observability stack in k3s.

carvin.chen@auckland.ac.nz, matt.pestle@auckland.ac.nz
Feb 2026

Create your nectar password for connecting to the cloud provider.
(see nectar tutorial)
https://tutorials.rc.nectar.org.au/openstack-cli/04-credentials

clouds.yaml - Put your clouds.yaml into place - looking like this:

```
clouds:
  openstack:
    auth:
      auth_url: https://identity.rc.nectar.org.au/v3/
      username: matt.pestle@auckland.ac.nz
      project_id: 76f84625ee51456b9f98ace08226f900
      password: "<secret_password>"
      user_domain_name: "Default"
    region_name: "Melbourne"
    interface: "public"
    identity_api_version: 3
```

dev and prod (or other environments) may have different cloud.yaml files,
so I've put my dev one into the dev directory.

Or equivalently match the cloud name in provider.tf somehow.


backend.tf - So far Matt has been unable to use nectar's object store to store the terraform
state file, so currently we are doing this locally and then using state_push
and state_pull so others (with access to our openstack project)
can use the same state. We have advised Sean Matheny about this (NeSI's object store works
for this purpose). He's investigating.

In the meantime, this backend.tf defines a local state file which can be pushed
to a Nectar object store using state_push, or pulled from using state_pull. So if you
want to adjust what Matt has done,
- state_pull
- make your terraform changes and apply
- state_push

so the next time someone else comes along they can do the same. There's no locking here with this method,
but there's few enough of us using this we can probably get away with it.

Matt created a container/bucket named terraform-states and this script is pushing the state file
to digitaltwins/dev/terraform.tfstate in that container
(should the bucket be named something a little more specific to this project??)


existing_stuff.tf data entities about stuff that was created outside terraform
in particular:
    - network names
    - image name used for the VM
    - the flavor used for the VM (r3.medium - 16GB RAM, eg.)
    - the keypair used for the VM (we are using one called drai-inn-keypair)

(note that the terraform defines a 100GB root file system volume, not the 8GB
that would normally arrive with r3.medium).

After the VM comes up and you have its IP, you can then set up your ssh configuration
so that 
    ssh abi_portal
gets you into the VM.

You can do this by putting this in your ~/.ssh/config:

```
Host abi_portal
    HostName 130.216.217.226 # or whatever the resulting IP is
    User ubuntu
    IdentityFile ~/keys/drai-inn-keypair.key
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
```

But one way or another, you need to get so you can get on the VM and then
put the appropriate definition in inventory/on-prem (we are keeping this
file in the repo, and it is hopefully up to date)

Set and export these environment variables with your secrets (see `env.template`):
- KC_HTTPS_KEY_STORE_PASSWORD (for the server.jks you created for https on keycloak)
- KC_CLIENT_SECRET            (this is the keycloak "api" client in the digitaltwins realm)
- SEEK_ADMIN_PASSWORD         (the admin user, the 1st user created in the seek system)
- KC_HTTPS_KEY_STORE_PASSWORD is used in util/create_server_jks to create a self-signed
cert used by keycloak, a step that needs to be done manually once, at some point. I
haven't made it part of the playbook. Maybe it should be?
- GRAFANA_ADMIN is used to set the admin password for grafana in build_observability_full.yaml

Then you can run the playbook build_all.yaml
```bash
  ansible-playbook build_all.yaml -i inventory/on-prem -l portal
```
which should leave you with a functioning digital twins system
(modulo the fix.sh that may need to be carried out, or anything else
that breaks it in the meantime).

This does all the steps the Chin-Chien has listed on

https://github.com/ABI-CTT-Group/digitaltwins-platform/blob/main/docs/deploying.md
(as at Nov 26 2025)

(None of the optional steps that Chin-Chien notes are done in this ansible -
this is just to get things up and running.
If you want other passwords, etc, you'll need to adjust accordingly).


NOTES:

- initially 8GB of RAM was used. This isn't enough. It was swapping and slow.
rebuilt with 16GB RAM (r3.medium - 16RAM4CPU). We are not authorised to construct
are own flavours (I'd probably try a 16GB RAM, 2cpu size for dev if I could).

- Hopefully everything is idempotent (in both the terraform and ansible stuff)
and running it multiple times won't hurt anything. If you manually change things
in the system, however, running ansible again may clobber something? Best to check that.
(note: portal3 is NOT idempotent - do not run multiple times)


TO DO:
- Get seek integrated with keycloak
- Get portal integrated with keycloak
- Figure out if you can just copy docker volumes to bring up another
  instance that looks like the copied one.
- Maybe figure out backups? Although if you solve the previous step, that's
  that backup strategy, isn't it? Just archive the docker volumes.

# Observability

- The work branch is `buildout+observability`. Merging into buildout when desired.
- Observability use grafana stack which deployed in a kubernetes cluster (light weight kubernetes, k3s)
- The components of grafana stack include grafana, loki, mimir, alloy, the related resource are stored in folder `/buildout/dev/observability`
- K9s is a high efficient tool to manage the k8s cluster and will be deployed by ansible to target VM

## Setup Instructions


- Switch to branch `buildout`, navigate to folder `/buildout/dev`
(the buildout+observability branch has been merged to just buildout)
- Ensure the GRAFANA_ADMIN_PASSWORD env variable is set with the value you want to use as
the grafana admin password (see GCP in mygen3 project, under the digital_twins_grafana_admin secret)
(see env.template)
- Run the ansible playbook `build_observability_full.yaml` to deploy all observability to target VM
```bash
  ansible-playbook build_observability_full.yaml -i inventory/on-prem -l portal
```
- restart docker with "docker compose down; docker compose up -d" . This is because the mimir
installation grabs port 80 and kills the digital twins portal. Still more work to do here.
Matt added the "--disable-traefik" in an attempt to avoid this port grab. Another option is
to change the port with an nginx:system:port value setting.
- Login to system with URL  http://the-vm-ip:30333 with admin $GRAFANA_ADMIN_PASSWORD
- The deployment will set the datasource and dashboards for both logs and metrics
- The dashboards are stored at folder `buildout/dev/observability/dashboards`, which will be applied as configmap in deployment
- The helm chart package file and the customized values.yaml of grafana,mimir,loki are in folder `buildout/dev/observability`
  User can adjust the configuration and resources request in the customized values.yaml
- Carvin has found that after you run build_observability_full.yaml, which restarts k3s, you need to:
```bash
kubectl -n loki port-forward svc/loki-gateway 3100:80 &
kubectl -n mimir port-forward svc/mimir-gateway  9005:8080 &
kubectl -n kube-system port-forward svc/metrics-server 8443:443 &
```
manually.
- the observability helm chars, customized values.yaml, and dashboard json files are all in directory /buildout/dev/observability
## backup of observability
The crontab will be installed to the VM , as well as a backup cronjob will be deployed and run everyday.
- the backup and restore scope includes:
   - Grafana data stored in the persistent volume of grafana namespace 
   - Log data in the persistent volume of loki namespace 
   - Metric data stored in the  directory within the MinIO persistent volume of the mimir namespace
- The number of backup files to retain can be configured in the backup script; it is currently set to 2.
- The restore script automatically restores from the most recent backup file by default.
- The backup directory is set to /home/ubuntu/data-backup/k3s-pvc
  - In nectar environment, the data-backup is mounted to a volume data-backup in the cloud.
  - If work in an isolated machine, please manually create the folder /home/ubuntu/data-backup/k3s-pvc for backup 
- The backup and restore script is at directory /buildout/dev/observability/backup
   please run restore_k3s_storage.sh -h to get the help of restore
- After restored data, please wait for 10 minutes for the system reindex the logs and metrics.
## Ports

Digital twins run up by itself seems to grab:
- 80
- 8080
- 8000, 8001, 8002, 8003, 8004
- 8008, 8009, 8010, 8011, 8012, 8014, 8015

Observability run up by itself seems to grab:
- 81
- 7443
- 6444
- 9005
- 10250
- and somewhere at the kernel level (k3s??) it's also clearly attaching 30333 to run grafana
(although this doesn't show up in `ss -tpna`)

There are a lot of other ports tied up, but only on localhost. So the above
are the ones that I think need to be addressed at a firewall level. Or, probably
better, if those don't need to be exposed, figure out how to bind them to 
localhost instead of 0.0.0.0.
