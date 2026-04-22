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

resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_3" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 81
  port_range_max    = 81
  description       = "port 81 from everywhere"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
}

#resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_8000" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8000
#  port_range_max    = 8000
#  description       = "port 8000 from everywhere - admin - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
#}

#resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_8001" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8001
#  port_range_max    = 8001
#  description       = "port 8001 from everywhere - admin - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_8004" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8004
#  port_range_max    = 8004
#  description       = "port 8004 from everywhere - admin - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_8009" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8009
#  port_range_max    = 8009
#  description       = "port 8009 from everywhere - rest api - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_8010" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8010
#  port_range_max    = 8010
#  description       = "port 8010 from everywhere - rest api - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "web_server_i_rule_80xx" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8000
#  port_range_max    = 8012
#  description       = "port 8000-8012 from everywhere"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server_i.id
#}

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

