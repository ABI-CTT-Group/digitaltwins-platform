import requests
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Assign airflow_admin to service-account-api in Keycloak.")
    parser.add_argument("--keycloak-url", required=True, help="Base URL of Keycloak (e.g., http://localhost/auth or https://dev.../auth)")
    parser.add_argument("--realm", default="digitaltwins", help="The realm to update")
    parser.add_argument("--admin-user", default="admin", help="Admin username")
    parser.add_argument("--admin-password", required=True, help="Admin password")
    
    args = parser.parse_args()
    
    # 1. Get Admin Access Token
    token_url = f"{args.keycloak_url}/realms/master/protocol/openid-connect/token"
    token_data = {
        "client_id": "admin-cli",
        "username": args.admin_user,
        "password": args.admin_password,
        "grant_type": "password"
    }
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    response = requests.post(token_url, data=token_data, verify=False)
    if not response.ok:
        print(f"❌ Failed to get admin token: {response.text}")
        sys.exit(1)
    access_token = response.json()["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 2. Get the user 'service-account-api'
    users_url = f"{args.keycloak_url}/admin/realms/{args.realm}/users"
    response = requests.get(users_url, headers=headers, params={"username": "service-account-api"}, verify=False)
    if not response.ok:
        print(f"❌ Failed to query users: {response.text}")
        sys.exit(1)
    users = response.json()
    if not users:
        print("❌ Error: service-account-api user not found")
        sys.exit(1)
    user_id = users[0]["id"]
    print(f"Found service-account-api user id: {user_id}")

    # 3. Get the 'airflow_admin' role
    roles_url = f"{args.keycloak_url}/admin/realms/{args.realm}/roles/airflow_admin"
    response = requests.get(roles_url, headers=headers, verify=False)
    if not response.ok:
        print(f"❌ Failed to get role airflow_admin: {response.text}")
        sys.exit(1)
    role = response.json()

    # 4. Map the role to the user
    mapping_url = f"{args.keycloak_url}/admin/realms/{args.realm}/users/{user_id}/role-mappings/realm"
    response = requests.post(mapping_url, headers=headers, json=[role], verify=False)
    if response.status_code == 204:
        print("✅ Successfully added airflow_admin role to service-account-api.")
    else:
        print(f"❌ Failed to add role: {response.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()
