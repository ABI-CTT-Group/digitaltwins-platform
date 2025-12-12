#!/bin/bash

CONTAINER_NAME="digitaltwins-platform-seek-1"

IP=$(curl -s ifconfig.me)

echo "Enabling desired SEEK features in container: $CONTAINER_NAME"

cat << RUBY_SCRIPT | docker exec -i "$CONTAINER_NAME" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
Seek::Config.site_base_host = "http://$IP:8001"
puts "Site base hostname set to: #{Seek::Config.site_base_host}"

RUBY_SCRIPT
