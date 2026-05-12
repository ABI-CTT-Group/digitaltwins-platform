variable "portal_disk_size" {
    type = number
    description = "size of portal root disk"
    default = 100
}

variable "wg_cidr" {
    type = string
    description = "cidr of walled_garden"
    default = "10.2.0.0/24"
}

variable "p_cidr" {
    type = string
    description = "cidr of public facing network"
    default = "192.168.2.0/24"
}

variable "dns" {
    type = list(string)
    description = "DNS server for public facing network"
    default = [ "130.216.1.1", "130.216.1.2" ]
}
