# Port on wg network/subnet for compute
resource "openstack_networking_port_v2" "port_auckland_wg_compute" {
  name       = "drai_compute_wg"
  network_id = openstack_networking_network_v2.n_wg.id
}

# security group on the port
resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_wg_compute" {
  port_id = openstack_networking_port_v2.port_auckland_wg_compute.id
  security_group_ids = [
    resource.openstack_networking_secgroup_v2.internal_compute.id
  ]
}

# compute VM

resource "openstack_compute_instance_v2" "compute" {
  name            = "drai_compute"
  flavor_id       = data.openstack_compute_flavor_v2.r3_medium.id
  key_pair        = data.openstack_compute_keypair_v2.drai_inn_keypair.id
  network {
    port =  openstack_networking_port_v2.port_auckland_wg_compute.id 
  }

  block_device {
    uuid                  = data.openstack_images_image_v2.portal_image2.id
    source_type           = "image"
    destination_type      = "volume"
    boot_index            = 0
    delete_on_termination = true
    volume_size           = var.portal_disk_size
    #volume_type           = "performance"
  }
}

## security groups on the port
#resource "openstack_networking_port_secgroup_associate_v2" "port_sec_group_compute" {
#  port_id = openstack_networking_port_v2.port_auckland_public_compute.id
#  security_group_ids = [
#    resource.openstack_networking_secgroup_v2.ssh_restricted_i.id
#    ,resource.openstack_networking_secgroup_v2.web_server_i.id
#  ]
#}
