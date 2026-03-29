# Port on auckland-public network/subnet for portal
resource "openstack_networking_port_v2" "port_auckland_public_portal" {
  name       = "drai_portal_public"
  network_id = data.openstack_networking_network_v2.auckland_public.id
}

# portal VM
resource "openstack_compute_instance_v2" "portal" {
  name            = "drai_portal"
  flavor_id       = data.openstack_compute_flavor_v2.m3_xxlarge.id
  key_pair        = data.openstack_compute_keypair_v2.drai_inn_keypair.id
  network {
    port =  openstack_networking_port_v2.port_auckland_public_portal.id 
  }

  block_device {
    uuid                  = data.openstack_images_image_v2.portal_image2.id
    source_type           = "image"
    destination_type      = "volume"
    boot_index            = 0
    delete_on_termination = true
    volume_size           = var.portal_disk_size
  }

user_data = <<-EOF
  #cloud-config
  # 1. Kill the background update engine
  package_update: false
  package_upgrade: false
    
  # 2. Prevent 'apt' locks and Prep the Podman Socket
  write_files:
    - path: /etc/apt/apt.conf.d/99manual-only
      content: |
        APT::Periodic::Update-Package-Lists "0";
        APT::Periodic::Unattended-Upgrade "0";
    - path: /etc/tmpfiles.d/podman-socket.conf
      content: |
        z /run/podman/podman.sock 0666 root root - -
        L+ /var/run/docker.sock - - - - /run/podman/podman.sock
      
  # 3. Secure the boot process
  runcmd: 
    # Stop the background update timers
    - [ systemctl, mask, apt-daily.timer, apt-daily-upgrade.timer ]
    
    # EMERGENCY KEY: Ensure UFW allows SSH before it locks the box
    - [ ufw, allow, 22/tcp ]
    - [ ufw, --force, enable ]
    
    # Start the system-wide socket and apply permissions
    - [ systemctl, enable, --now, podman.socket ]
    - [ systemd-tmpfiles, --create, /etc/tmpfiles.d/podman-socket.conf ]
EOF
}

# ssh_restricted security group on the port
resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_portal" {
  port_id = openstack_networking_port_v2.port_auckland_public_portal.id
  security_group_ids = [
     resource.openstack_networking_secgroup_v2.ssh_restricted_i.id
    ,resource.openstack_networking_secgroup_v2.web_server_i.id
  ]
}

resource "openstack_compute_volume_attach_v2" "vm_portal_docker_cache" {
  instance_id = openstack_compute_instance_v2.portal.id
  volume_id   = data.openstack_blockstorage_volume_v3.docker_cache2.id
  device = "/dev/vdb"
}
