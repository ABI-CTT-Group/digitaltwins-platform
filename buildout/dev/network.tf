resource "openstack_networking_network_v2" "n_wg" {
    name           = "walled_garden"
    admin_state_up = "true"
}

resource "openstack_networking_subnet_v2" "sn_wg" {
    name       = "walled_garden"
    network_id = openstack_networking_network_v2.n_wg.id
    cidr       = var.wg_cidr
}

resource "openstack_networking_network_v2" "n_p" {
    name           = "public_facing"
    admin_state_up = "true"
}

resource "openstack_networking_subnet_v2" "sn_p" {
    name       = "public_facing"
    network_id = openstack_networking_network_v2.n_p.id
    cidr       = var.p_cidr
}

resource "openstack_networking_router_v2" "p_router" {
    name                = "public_router"
    admin_state_up      = true
    external_network_id = data.openstack_networking_network_v2.auckland.id
}

resource "openstack_networking_router_interface_v2" "p_router_iface_p" {
  router_id = openstack_networking_router_v2.p_router.id
  subnet_id = openstack_networking_subnet_v2.sn_p.id
}
