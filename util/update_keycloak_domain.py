"""
How to use this script:


# Install the requests library if you don't have it
pip install requests
# Run the script to add a new domain
python3 update_keycloak_domain.py \
  --keycloak-url "http://localhost/auth" \
  --admin-password "admin" \
  --new-domain "https://prod-digitaltwins.com"


1. Non-Destructive: It modifies your live Keycloak database over the API, meaning you don't lose any existing users, passwords, or data.
2. Idempotent: It checks if the URL already exists before appending, so it's safe to run multiple times.
3. Flexible: You can point the --keycloak-url parameter to any deployment (e.g., your remote VM gateway) to run it remotely without needing to SSH into the server.
"""

import requests
import json
import argparse

def main():
    parser = argparse.ArgumentParser(description="Add a new domain to Keycloak clients.")
    parser.add_argument("--keycloak-url", required=True, help="Base URL of Keycloak (e.g., http://localhost/auth)")
    parser.add_argument("--realm", default="digitaltwins", help="The realm to update")
    parser.add_argument("--admin-user", default="admin", help="Admin username")
    parser.add_argument("--admin-password", required=True, help="Admin password")
    parser.add_argument("--new-domain", required=True, help="The new domain to add (e.g., https://new-domain.com)")
    
    args = parser.parse_args()
    
    # 1. Get Admin Access Token
    token_url = f"{args.keycloak_url}/realms/master/protocol/openid-connect/token"
    token_data = {
        "client_id": "admin-cli",
        "username": args.admin_user,
        "password": args.admin_password,
        "grant_type": "password"
    }
    
    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    access_token = response.json()["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # 2. Get all clients in the realm
    clients_url = f"{args.keycloak_url}/admin/realms/{args.realm}/clients"
    clients_response = requests.get(clients_url, headers=headers)
    clients_response.raise_for_status()
    clients = clients_response.json()
    
    print(f"Found {len(clients)} clients in realm '{args.realm}'.")
    
    # 3. Update each client
    for client in clients:
        client_id = client.get("clientId")
        updated = False
        
        # Update redirectUris
        redirect_uris = client.get("redirectUris", [])
        new_redirects = list(redirect_uris)
        
        for uri in redirect_uris:
            if uri.startswith("http://localhost"):
                # Special handling for SEEK since it's hosted at /seek and has a port locally
                if client_id == "seek" and "/users/auth/seek/callback" in uri:
                    new_uri = f"{args.new_domain}/seek/users/auth/seek/callback"
                else:
                    new_uri = uri.replace("http://localhost", args.new_domain)
                    
                if new_uri not in new_redirects:
                    new_redirects.append(new_uri)
                    updated = True

        # Update webOrigins
        web_origins = client.get("webOrigins", [])
        new_origins = list(web_origins)
        
        for origin in web_origins:
            if origin.startswith("http://localhost"):
                new_origin = origin.replace("http://localhost", args.new_domain)
                if new_origin not in new_origins:
                    new_origins.append(new_origin)
                    updated = True
                    
        # Save if changes were made
        if updated:
            client["redirectUris"] = new_redirects
            client["webOrigins"] = new_origins
            
            update_url = f"{clients_url}/{client['id']}"
            update_response = requests.put(update_url, headers=headers, json=client)
            
            if update_response.status_code == 204:
                print(f"✅ Successfully updated client: {client_id}")
            else:
                print(f"❌ Failed to update {client_id}: {update_response.text}")

if __name__ == "__main__":
    main()
