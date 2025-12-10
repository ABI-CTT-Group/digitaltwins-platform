# I like to have this handy if terraform turns to custard
# and you don't want to faff with it and just want to start over

openstack server delete drai_portal
openstack port delete drai_portal_public
openstack volume delete drai_portal
openstack security group delete drai_web_server drai_ssh_restricted
