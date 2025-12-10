terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
    }
  }
}

# Set env variable "export OS_CLOUD=openstack"
# with this and clouds.yaml to work in the abi project
# if you're in this directory
provider "openstack" {
  cloud = "openstack"
}
