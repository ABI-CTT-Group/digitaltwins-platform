resource "openstack_networking_secgroup_v2" "web_server" {
  name        = "drai_web_server"
  description = "allow 80 and 443 from world"
}

resource "openstack_networking_secgroup_rule_v2" "web_server_rule_1" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  description       = "port 80 from everywhere"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
}

resource "openstack_networking_secgroup_rule_v2" "web_server_rule_2" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  description       = "port 443 from everywhere"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
}

resource "openstack_networking_secgroup_rule_v2" "web_server_rule_8001" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8001
  port_range_max    = 8001
  description       = "port 8001 from everywhere - admin - close later?"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
}

resource "openstack_networking_secgroup_rule_v2" "web_server_rule_8004" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8004
  port_range_max    = 8004
  description       = "port 8004 from everywhere - admin - close later?"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
}

resource "openstack_networking_secgroup_rule_v2" "web_server_rule_8010" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8010
  port_range_max    = 8010
  description       = "port 8010 from everywhere - rest api - close later?"
  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
}

#resource "openstack_networking_secgroup_rule_v2" "web_server_rule_8002" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8002
#  port_range_max    = 8002
#  description       = "port 8002 from everywhere - airflow - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "web_server_rule_8008" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8008
#  port_range_max    = 8008
#  description       = "port 8008 from everywhere - jupyterlab - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "web_server_rule_8009" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8009
#  port_range_max    = 8009
#  description       = "port 8009 from everywhere - keycloak - close later?"
#  security_group_id = resource.openstack_networking_secgroup_v2.web_server.id
#}

resource "openstack_networking_secgroup_v2" "ssh_restricted" {
  name        = "drai_ssh_restricted"
  description = "allow 22 from restricted list"
}

resource "openstack_networking_secgroup_rule_v2" "ssh_restricted_rule_1" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "163.7.144.201/32"
  description       = "port 22 from mp gendev"
  security_group_id = resource.openstack_networking_secgroup_v2.ssh_restricted.id
}

resource "openstack_networking_secgroup_rule_v2" "ssh_restricted_rule_2" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  description       = "port 22 from world"
  security_group_id = resource.openstack_networking_secgroup_v2.ssh_restricted.id
}

# Possible future stuff below
#
#resource "openstack_networking_secgroup_v2" "postgres_db" {
#  name        = "postgres_db"
#  description = "postgres DB rules"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "postgres_db_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 5432
#  port_range_max    = 5432
#  description       = "port 5432 within group"
#  remote_group_id   = openstack_networking_secgroup_v2.postgres_db.id
#  security_group_id = resource.openstack_networking_secgroup_v2.postgres_db.id
#}
#
#resource "openstack_networking_secgroup_v2" "nfs" {
#  name        = "nfs"
#  description = "NFS rules"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "nfs_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 2049
#  port_range_max    = 2049
#  description       = "port 2049 tcp"
#  security_group_id = resource.openstack_networking_secgroup_v2.nfs.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "nfs_rule_2" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "udp"
#  port_range_min    = 2049
#  port_range_max    = 2049
#  description       = "port 2049 udp"
#  security_group_id = resource.openstack_networking_secgroup_v2.nfs.id
#}
#
#resource "openstack_networking_secgroup_v2" "audit_api" {
#  name        = "audit_api"
#  description = "audit_api rules"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "audit_api_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8080
#  port_range_max    = 8080
#  description       = "port 8080 tcp"
#  security_group_id = resource.openstack_networking_secgroup_v2.audit_api.id
#}
#
#resource "openstack_networking_secgroup_v2" "rems_restricted" {
#  name        = "rems_restricted"
#  description = "allow 8443 from restricted list"
#}
#
## k8s presents from one of these...
## 163.7.144.143   # seems to be this one
## 
## 163.7.144.201
## 163.7.145.194
##
## 163.7.145.121
#resource "openstack_networking_secgroup_rule_v2" "rems_restricted_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8443
#  port_range_max    = 8443
#  remote_ip_prefix  = var.keycloak_presenting_ip
#  description       = "port 8443 from keycloak k8s"
#  security_group_id = resource.openstack_networking_secgroup_v2.rems_restricted.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "rems_restricted_rule_2" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 8443
#  port_range_max    = 8443
#  remote_group_id   = openstack_networking_secgroup_v2.rems_restricted.id
#  description       = "port 8443 within group"
#  security_group_id = resource.openstack_networking_secgroup_v2.rems_restricted.id
#}
#
### This can go if Carvin can put rems_restricted onto the k8s VM
##resource "openstack_networking_secgroup_rule_v2" "rems_restricted_rule_3" {
##  direction         = "ingress"
##  ethertype         = "IPv4"
##  protocol          = "tcp"
##  port_range_min    = 8443
##  port_range_max    = 8443
##  remote_ip_prefix  = "163.7.144.201/32"
##  description       = "port 8443 from gendev"
##  security_group_id = resource.openstack_networking_secgroup_v2.rems_restricted.id
##}
#
#resource "openstack_networking_secgroup_v2" "ssh_lander" {
#  name        = "ssh_lander"
#  description = "allow 22 from lander"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "ssh_lander_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 22
#  port_range_max    = 22
#  # This remote_ip_prefix is ugly, but the only way I've found to get
#  # terraform from not entering a non-idempotent state with this security group definition
#  remote_ip_prefix  = format("%s/32",openstack_networking_port_v2.port_n_r_lander.all_fixed_ips.0)
#  description       = "port 22 from lander via rakeiora"
#  security_group_id = openstack_networking_secgroup_v2.ssh_lander.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "ssh_lander_rule_2" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 22
#  port_range_max    = 22
#  # This remote_ip_prefix is ugly, but the only way I've found to get
#  # terraform from not entering a non-idempotent state with this security group definition
#  remote_ip_prefix  = format("%s/32",openstack_networking_port_v2.port_n_wg_lander.all_fixed_ips.0)
#  description       = "port 22 from lander via walled_garden"
#  security_group_id = openstack_networking_secgroup_v2.ssh_lander.id
#}
#
#resource "openstack_networking_secgroup_v2" "rabbitmq" {
#  name        = "rabbitmq"
#  description = "allow 5672 for mq"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "rabbitmq_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 5672
#  port_range_max    = 5672
#  remote_group_id      = openstack_networking_secgroup_v2.rabbitmq.id
#  description       = "port 5672 within group"
#  security_group_id = openstack_networking_secgroup_v2.rabbitmq.id
#}
#
#resource "openstack_networking_secgroup_v2" "compute" {
#  name        = "compute"
#  description = "compute instances"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "compute_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 22
#  port_range_max    = 22
#  description       = "port 22 from within group"
#  security_group_id = resource.openstack_networking_secgroup_v2.compute.id
#  remote_group_id   = resource.openstack_networking_secgroup_v2.compute.id
#}
#
#resource "openstack_networking_secgroup_v2" "wg_data" {
#  name        = "wg_data"
#  description = "wg_data instances"
#}
#
#resource "openstack_networking_secgroup_rule_v2" "wg_data_rule_1" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 80
#  port_range_max    = 80
#  description       = "port 80"
#  security_group_id = resource.openstack_networking_secgroup_v2.wg_data.id
#  remote_group_id   = resource.openstack_networking_secgroup_v2.wg_data.id
#}
#
#resource "openstack_networking_secgroup_rule_v2" "wg_data_rule_2" {
#  direction         = "ingress"
#  ethertype         = "IPv4"
#  protocol          = "tcp"
#  port_range_min    = 443
#  port_range_max    = 443
#  description       = "port 443"
#  security_group_id = resource.openstack_networking_secgroup_v2.wg_data.id
#  remote_group_id   = resource.openstack_networking_secgroup_v2.wg_data.id
#}
#
#resource "openstack_networking_secgroup_v2" "dummy" {
#  name        = "dummy"
#  description = "dummy group with no rules"
#}
#
