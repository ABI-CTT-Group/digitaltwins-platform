#!/bin/bash
# Script to create a SEEK admin user
# Can create users with local password or prepare them for Keycloak Omniauth
# Usage: 
#   Local user: ./create-admin-user.sh <username> <password> <email>
#   Keycloak user: ./create-admin-user.sh <username> -keycloak <email>

CONTAINER_NAME="digitaltwins-platform-seek-1"
USERNAME=${1:-}
PASSWORD=${2:-}
EMAIL=${3:-}

if [ -z "$USERNAME" ]; then
  echo "Usage: $0 <username> [password|'-keycloak'] <email>"
  echo ""
  echo "Examples:"
  echo "  # Create local user with password"
  echo "  $0 admin mypassword admin@example.com"
  echo ""
  echo "  # Create Keycloak user (no password needed)"
  echo "  $0 admin -keycloak admin@example.com"
  exit 1
fi

# Check if using Keycloak
KEYCLOAK_MODE=false
if [ "$PASSWORD" = "-keycloak" ]; then
  KEYCLOAK_MODE=true
  PASSWORD=""
fi

echo "Creating admin user: $USERNAME"
echo "Container: $CONTAINER_NAME"
echo "Email: $EMAIL"
[ "$KEYCLOAK_MODE" = true ] && echo "Mode: Keycloak (no local password)" || echo "Mode: Local authentication"
echo ""

cat << RUBY_SCRIPT | docker exec -i "$CONTAINER_NAME" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
user = User.find_by(login: "$USERNAME")
if user
  puts "User '$USERNAME' already exists"
else
  user = User.new
  user.login = "$USERNAME"
  
  # Only set password if not in Keycloak mode
  unless "$KEYCLOAK_MODE" == "true"
    user.password = "$PASSWORD"
    user.password_confirmation = "$PASSWORD"
  end
  
  person = Person.new
  person.email = "$EMAIL"
  person.first_name = "$USERNAME"
  person.last_name = "User"
  person.user = user
  
  # Disable authorization checks for user creation
  Seek::Permissions::Authorization.disable_authorization_checks do
    if person.save
      # Make the person a system admin
      person.is_admin = true
      person.save
      
      # Activate the user to skip email validation
      user.activated_at = Time.current
      user.activation_code = nil
      user.save
      
      puts "✓ User '$USERNAME' created successfully as administrator"
      puts "  Email: $EMAIL"
      if "$KEYCLOAK_MODE" == "true"
        puts "  Mode: Keycloak Omniauth (login via Keycloak)"
      else
        puts "  Mode: Local password (login with username and password)"
      end
    else
      puts "✗ Failed to create user: #{person.errors.full_messages.join(', ')}"
    end
  end
end
RUBY_SCRIPT
