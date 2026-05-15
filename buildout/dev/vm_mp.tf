# Port on auckland-wg network/subnet for mp
resource "openstack_networking_port_v2" "port_auckland_wg_mp" {
  name       = "drai_mp_wg"
  network_id = openstack_networking_network_v2.n_wg.id
}

# Port on auckland-public network/subnet for portal
resource "openstack_networking_port_v2" "port_auckland_public_mp" {
  name       = "drai_mp_public"
  network_id = openstack_networking_network_v2.n_p.id
}

resource "openstack_networking_floatingip_associate_v2" "fip_mp" {
  floating_ip = data.openstack_networking_floatingip_v2.floatip_dev.address
  port_id     = openstack_networking_port_v2.port_auckland_public_mp.id
}

# mp VM
resource "openstack_compute_instance_v2" "mp" {
  name            = "drai_mp"
  flavor_id       = data.openstack_compute_flavor_v2.r3_medium.id
  key_pair        = data.openstack_compute_keypair_v2.drai_inn_keypair.id
  network {
    port =  openstack_networking_port_v2.port_auckland_public_mp.id 
  }
  network {
    port =  openstack_networking_port_v2.port_auckland_wg_mp.id 
  }

  block_device {
    uuid                  = data.openstack_images_image_v2.portal_image2.id
    source_type           = "image"
    destination_type      = "volume"
    boot_index            = 0
    delete_on_termination = true
    volume_size           = 70
    volume_type           = "performance"
  }
}

# security groups on the port
resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_mp" {
  port_id = openstack_networking_port_v2.port_auckland_public_mp.id
  security_group_ids = [
    resource.openstack_networking_secgroup_v2.ssh_restricted_i.id
    ,resource.openstack_networking_secgroup_v2.web_server_i.id
  ]
}

# ssh_restricted security group on the port
resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_mp_wg" {
  port_id = openstack_networking_port_v2.port_auckland_wg_mp.id
  security_group_ids = [
    resource.openstack_networking_secgroup_v2.internal_compute.id
  ]
}


# docker_cache volume
resource "openstack_blockstorage_volume_v3" "docker_cache" {
  name = "docker_cache"
  size = 50
  availability_zone = "auckland"
}

resource "openstack_compute_volume_attach_v2" "vm_mp_docker_cache" {
  instance_id = openstack_compute_instance_v2.mp.id
  volume_id   = openstack_blockstorage_volume_v3.docker_cache.id
  device = "/dev/vdb"
}
