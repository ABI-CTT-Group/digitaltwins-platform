# Port on auckland-public network/subnet for portal
resource "openstack_networking_port_v2" "port_auckland_public_cc" {
  name       = "drai_cc_public"
  network_id = data.openstack_networking_network_v2.auckland_public.id
}

# portal VM
resource "openstack_compute_instance_v2" "cc" {
#  count = 0
  name            = "drai_cc"
  flavor_id       = data.openstack_compute_flavor_v2.m3_xlarge.id
  key_pair        = data.openstack_compute_keypair_v2.drai_inn_keypair.id
  network {
    port =  openstack_networking_port_v2.port_auckland_public_cc.id
  }

  block_device {
    uuid                  = data.openstack_images_image_v2.portal_image.id
    source_type           = "image"
    destination_type      = "volume"
    boot_index            = 0
    delete_on_termination = true
    volume_size           = var.portal_disk_size
  }
}

# The Volume
resource "openstack_blockstorage_volume_v3" "data_backup" {
  name = "data-backup"
  size = 100
}

# ssh_restricted security group on the port
resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_cc" {
  port_id = openstack_networking_port_v2.port_auckland_public_cc.id
  security_group_ids = [
    resource.openstack_networking_secgroup_v2.ssh_restricted.id,
    resource.openstack_networking_secgroup_v2.web_server.id,
    data.openstack_networking_secgroup_v2.digital_twins.id
  ]
}

resource "openstack_compute_volume_attach_v2" "vm_cc_data_backup" {
  instance_id = openstack_compute_instance_v2.cc.id
  volume_id   = openstack_blockstorage_volume_v3.data_backup.id
  device = "/dev/vdb"
}
