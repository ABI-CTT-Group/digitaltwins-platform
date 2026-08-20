import requests
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Fix admin-cli client in Keycloak.")
    parser.add_argument("--keycloak-url", required=True, help="Base URL of Keycloak (e.g., http://localhost/auth)")
    parser.add_argument("--realm", default="digitaltwins", help="The realm to update")
    parser.add_argument("--admin-user", default="admin", help="Admin username")
    parser.add_argument("--admin-password", required=True, help="Admin password")
    parser.add_argument("--client-secret", required=True, help="Secret to set for admin-cli")
    
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
    
    # 2. Get admin-cli client in the target realm
    clients_url = f"{args.keycloak_url}/admin/realms/{args.realm}/clients"
    clients_response = requests.get(clients_url, headers=headers, params={"clientId": "admin-cli"})
    clients_response.raise_for_status()
    clients = clients_response.json()
    
    if not clients:
        print("Error: admin-cli client not found in realm.")
        sys.exit(1)
        
    admin_cli = clients[0]
    admin_cli_id = admin_cli["id"]
    print(f"Found admin-cli client with id: {admin_cli_id}")
    
    # 3. Update admin-cli to be confidential with service accounts enabled
    admin_cli["publicClient"] = False
    admin_cli["serviceAccountsEnabled"] = True
    admin_cli["secret"] = args.client_secret
    admin_cli["clientAuthenticatorType"] = "client-secret"
    
    update_url = f"{clients_url}/{admin_cli_id}"
    update_response = requests.put(update_url, headers=headers, json=admin_cli)
    if update_response.status_code == 204:
        print("✅ Successfully updated admin-cli client.")
    else:
        print(f"❌ Failed to update admin-cli: {update_response.text}")
        sys.exit(1)
        
    # 4. Get service account user for admin-cli
    sa_url = f"{clients_url}/{admin_cli_id}/service-account-user"
    sa_response = requests.get(sa_url, headers=headers)
    sa_response.raise_for_status()
    sa_user = sa_response.json()
    sa_user_id = sa_user["id"]
    print(f"Found service account user id: {sa_user_id}")
    
    # 5. Get realm-management client
    realm_mgmt_response = requests.get(clients_url, headers=headers, params={"clientId": "realm-management"})
    realm_mgmt_response.raise_for_status()
    realm_mgmt = realm_mgmt_response.json()[0]
    realm_mgmt_id = realm_mgmt["id"]
    
    # 6. Get view-users and view-realm roles from realm-management
    roles_url = f"{args.keycloak_url}/admin/realms/{args.realm}/clients/{realm_mgmt_id}/roles"
    roles_response = requests.get(roles_url, headers=headers)
    roles_response.raise_for_status()
    roles = roles_response.json()
    
    roles_to_assign = []
    for role in roles:
        if role["name"] in ["view-users", "view-realm", "query-users", "manage-users", "query-realms"]:
            roles_to_assign.append(role)
            
    print(f"Assigning {len(roles_to_assign)} roles to service account...")
    
    # 7. Map roles to service account
    mapping_url = f"{args.keycloak_url}/admin/realms/{args.realm}/users/{sa_user_id}/role-mappings/clients/{realm_mgmt_id}"
    mapping_response = requests.post(mapping_url, headers=headers, json=roles_to_assign)
    if mapping_response.status_code == 204:
        print("✅ Successfully mapped realm-management roles to admin-cli service account.")
    else:
        print(f"❌ Failed to map roles: {mapping_response.text}")

if __name__ == "__main__":
    main()
