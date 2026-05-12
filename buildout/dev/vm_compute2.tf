# Port on wg network/subnet for compute2
resource "openstack_networking_port_v2" "port_auckland_wg_compute2" {
  name       = "drai_compute2_wg"
  network_id = openstack_networking_network_v2.n_wg.id
}

# compute2 VM

resource "openstack_compute_instance_v2" "compute2" {
  name            = "drai_compute2"
  flavor_id       = data.openstack_compute_flavor_v2.r3_medium.id
  key_pair        = data.openstack_compute_keypair_v2.drai_inn_keypair.id
  network {
    port =  openstack_networking_port_v2.port_auckland_wg_compute2.id 
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
