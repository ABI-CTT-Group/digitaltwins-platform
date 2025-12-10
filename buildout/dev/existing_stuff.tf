# Existing entities in openstack that are used
#

data "openstack_networking_network_v2"  "auckland_public"       { name = "auckland-public" }
data "openstack_networking_network_v2"  "auckland_public_data"  { name = "auckland-public-data" }

data "openstack_images_image_v2" "portal_image"          { name = "NeCTAR Ubuntu 22.04 LTS (Jammy) amd64 (with Docker)" }

data "openstack_compute_flavor_v2"      "r3_medium"      { name = "r3.medium" }
data "openstack_compute_flavor_v2"      "m3_medium"      { name = "m3.medium" }

data "openstack_compute_keypair_v2"     "drai_inn_keypair"    { name = "drai-inn-keypair" }

data "openstack_networking_secgroup_v2" "digital_twins"         { name = "DigitalTWINS platform" }


# templates...
#data "openstack_images_image_v2"        "nesi-rocky-9-upstream"   {
#    name = "nesi-rocky-9-upstream.20251009"
#    visibility = "community"
#}
#data "openstack_images_image_v2" "portal_baseline_image" { name = "drai_portal_baseline_20251208" }
#data "openstack_blockstorage_volume_v3" "database"                { name = "database_dev" }
#data "openstack_blockstorage_volume_v3" "htsget_public"           { name = "htsget_public" }
#data "openstack_blockstorage_volume_v3" "space_ranger"            { name = "space_ranger" }
#data "openstack_networking_floatingip_v2" "floatip_jupyter"       { address = "163.7.145.164" }
#data "openstack_networking_network_v2"  "n_r"                { name = "n_r" }
#data "openstack_networking_network_v2"  "n_wg"               { name = "n_wg" }
#data "openstack_networking_subnet_v2"   "sn_r"               { name = "sn_r" }
#data "openstack_networking_subnet_v2"   "sn_wg"              { name = "sn_wg" }
#data "openstack_networking_secgroup_v2" "ssh_lander"         { name = "ssh_lander" }
#data "openstack_networking_port_v2"   "gen3_r_ip"     { name = "gen3_r_ip" }
