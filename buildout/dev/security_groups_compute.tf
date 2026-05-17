resource "openstack_networking_secgroup_v2" "web_server_compute" {
  name        = "drai_web_server_compute"
  description = "allow appropriate port traffic for web apps"

  # THIS IS THE MAGIC SWITCH. 
  # It prevents Terraform from creating the default allow-all egress rules.
  delete_default_rules = true
}

resource "openstack_networking_secgroup_rule_v2" "web_server_compute_rule_1" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8002
  port_range_max    = 8016
  description       = "port 8002-8016 from abi_newbox"
  remote_ip_prefix  = "130.216.208.19/32"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server_compute.id
}
