PUBLIC_FACING_IF=eth0
WALLED_GARDEN_IF=eth1
WALLED_GARDEN_CIDR="10.2.0.0/24"

sudo ufw allow from $WALLED_GARDEN_CIDR to any port 8000
sudo ufw allow from $WALLED_GARDEN_CIDR to any port 8002
sudo ufw allow from $WALLED_GARDEN_CIDR to any port 8010
sudo ufw allow from $WALLED_GARDEN_CIDR to any port 8011
sudo ufw allow from $WALLED_GARDEN_CIDR to any port 8013
sudo ufw allow from $WALLED_GARDEN_CIDR to any port 8016

# Allow forwarding (so portal can act as jump host)
sudo ufw route allow in on $PUBLIC_FACING_IF out on $WALLED_GARDEN_IF
sudo ufw allow out to $WALLED_GARDEN_CIDR
