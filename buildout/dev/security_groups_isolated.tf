resource "openstack_networking_secgroup_v2" "web_server_i" {
  name        = "drai_web_server_i"
  description = "allow appropriate port traffic for web apps"

  # THIS IS THE MAGIC SWITCH. 
  # It prevents Terraform from creating the default allow-all egress rules.
  delete_default_rules = true
}

resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_1" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  description       = "port 80 from everywhere"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
}

resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_2" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  description       = "port 443 from everywhere"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
}

resource "openstack_networking_secgroup_v2" "ssh_restricted_i" {
  name        = "drai_ssh_restricted_i"
  description = "allow 22 from restricted list"

  # THIS IS THE MAGIC SWITCH. 
  # It prevents Terraform from creating the default allow-all egress rules.
  delete_default_rules = true
}

resource "openstack_networking_secgroup_rule_v2" "ssh_restricted_i_rule_1" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "163.7.144.201/32"
  description       = "port 22 from mp gendev"
  security_group_id = resource.openstack_networking_secgroup_v2.ssh_restricted_i.id
}

resource "openstack_networking_secgroup_rule_v2" "ssh_restricted_i_rule_2" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  description       = "port 22 from world"
  security_group_id = resource.openstack_networking_secgroup_v2.ssh_restricted_i.id
}

resource "openstack_networking_secgroup_v2" "internal_compute" {
  name        = "internal-compute"
  description = "Allow all traffic between VMs in this group"
}

resource "openstack_networking_secgroup_rule_v2" "internal_ingress" {
  direction         = "ingress"
  ethertype         = "IPv4"
  security_group_id = openstack_networking_secgroup_v2.internal_compute.id
  remote_group_id   = openstack_networking_secgroup_v2.internal_compute.id
}

resource "openstack_networking_secgroup_rule_v2" "internal_ingress_v6" {
  direction         = "ingress"
  ethertype         = "IPv6"
  security_group_id = openstack_networking_secgroup_v2.internal_compute.id
  remote_group_id   = openstack_networking_secgroup_v2.internal_compute.id
}
