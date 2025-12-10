How to build out digital twins platform (terraform/ansible)
on an openstack cloud platform (here we use nectar).

Mod

matt.pestle@auckland.ac.nz
Nov 2025

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


backend.tf - So far I have been unable to use nectar's object store to store the terraform
state file, so currently I am doing this locally and then using state_push
and state_pull so others (with access to our openstack project)
can use the same state. Have advised Sean Matheny about this (NeSI's object store works
for this purpose). He's investigating.

In the meantime, this backend.tf defines a local state file which can be pushed
to a Nectar object store using state_push, or pulled from using state_pull. So if you
want to adjust what I have done,
- state_pull
- make your terraform changes and apply
- state_push

so the next time I come along I can do the same. There's no locking here with this method,
but there's few enough of us using this we can probably get away with it.

I created a container/bucket named terraform-states and I am pushing the state file
to digitaltwins/dev/terraform.tfstate in that container
(I wonder if my bucket should be named something a little more specific to this project??)


existing_stuff.tf data entities about stuff that was created outside terraform
in particular:
    - network names
    - image name used for the VM
    - the flavor used for the VM (r3.medium - 16GB RAM)
    - the keypair used for the VM (I created one called drai_keypair)

(note that my terraform defines a 100GB root file system volume, not the 8GB
that would normally arrive with r3.medium).

After the VM comes up and you have its IP, I have then set up my ssh configuration
so that 
    ssh abi_portal
gets me into the VM.

I personally did this by putting this in my ~/.ssh/config:

Host abi_portal
    HostName 130.216.217.226 # or whatever the resulting IP is
    User ubuntu
    IdentityFile ~/keys/drai-inn-keypair.key
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

But one way or another, you need to get so you can get on the VM and then
put the appropriate definition in inventory/on-prem

Set and export these 3 environment variables with your secrets:
KC_HTTPS_KEY_STORE_PASSWORD (for the server.jks you created for https on keycloak)
KC_CLIENT_SECRET            (this is the keycloak "api" client in the digitaltwins realm)
SEEK_ADMIN_PASSWORD         (the admin user, the 1st user created in the seek system)

Then you can run the playbook
build_all.yaml
which should leave you with a functioning system
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
- You should manually change the admin password on the keycloak instance
  (it's admin/admin by default)
- Get seek integrated with keycloak
- Get portal integrated with keycloak
- Figure out if you can just copy docker volumes to bring up another
  instance that looks like the copied one.
- Maybe figure out backups? Although if you solve the previous step, that's
  that backup strategy, isn't it? Just archive the docker volumes.
