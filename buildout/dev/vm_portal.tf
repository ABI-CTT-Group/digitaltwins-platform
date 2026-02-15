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
    uuid                  = data.openstack_images_image_v2.portal_image.id
    source_type           = "image"
    destination_type      = "volume"
    boot_index            = 0
    delete_on_termination = true
    volume_size           = var.portal_disk_size
  }
}

# ssh_restricted security group on the port
resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_portal" {
  port_id = openstack_networking_port_v2.port_auckland_public_portal.id
  security_group_ids = [
    resource.openstack_networking_secgroup_v2.ssh_restricted.id,
    resource.openstack_networking_secgroup_v2.web_server.id,
    data.openstack_networking_secgroup_v2.digital_twins.id
  ]
}