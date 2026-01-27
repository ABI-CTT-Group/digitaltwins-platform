#!/bin/bash
# Script to generate a SEEK API token and put it into the api configs.ini file
# Usage: 
#   ./generate-token.sh [username] # default username is "admin""

SEEK_TOKEN_FILE_NAME=${SEEK_TOKEN_FILE_NAME:=~/keys/seek_api_token.txt}
CONTAINER_NAME="digitaltwins-platform-seek-1"
USERNAME=${1:-admin}
CONFIG_FILE=~/digitaltwins-platform/services/api/digitaltwins-api/configs.ini
ENV_FILE=~/digitaltwins-platform/.env

[[ -f "$CONFIG_FILE" ]] || {
    echo "No config file $CONFIG_FILE"
    exit 1
}

API_TOKEN=$(cat << RUBY_SCRIPT | docker exec -i $CONTAINER_NAME bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
# Find the user (adjust username as needed)
user = User.find_by(login: "$USERNAME")

if user
  # Create a new API token
  token = ApiToken.new
  token.user = user
  token.title = "API token"

  if token.save
    #puts "✓ API Token generated successfully:"
    #puts "Token: #{token.token}"
    puts "#{token.token}"
  else
    puts "✗ Failed to create token: #{token.errors.full_messages.join(', ')}"
  end
else
  puts "✗ User not found"
end
RUBY_SCRIPT
) || {
   echo "$API_TOKEN"
   exit 1
}

sed -i "s/api_token=.*/api_token=\"$API_TOKEN\"/g" $CONFIG_FILE
sed -i "s/SEEK_API_TOKEN=.*/SEEK_API_TOKEN=\"$API_TOKEN\"/g" $ENV_FILE
echo $API_TOKEN > "$SEEK_TOKEN_FILE_NAME"
