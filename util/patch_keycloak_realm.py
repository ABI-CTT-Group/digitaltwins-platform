"""
Keycloak Realm Patcher

This script patches the Keycloak realm configuration JSON file to include a target host's URIs.

How to apply the changes made by this script:
1. For Staging/Production Deployment (Fresh boot):
   No action is needed. When Keycloak boots up for the first time in the new environment, 
   it will import the patched JSON file automatically (--import-realm).

2. To update an existing local Keycloak without losing data (Via UI):
   - Go to the Keycloak Admin Console (http://localhost/auth/admin/).
   - Click 'Realm Settings' on the left menu (in the digitaltwins realm).
   - In the top right corner, click 'Action' dropdown and select 'Partial Import'.
   - Upload the updated 'services/keycloak/import/digitaltwins-realm.json' file.

3. Nuke and Re-import Locally (Warning: Loses local users/data):
   If you want to force Keycloak to re-import locally on boot, you must wipe the 
   database volume so it acts like a first boot:
   `docker-compose down -v` then `docker-compose up -d`.
"""
import json
import argparse
import os


def patch_realm(target_host, file_path=None):
    """
    Patches the Keycloak realm configuration JSON file to include a target host's URIs.
    This ensures that when deploying to a new environment, Keycloak clients (like the frontend,
    SEEK, API, etc.) have the correct redirect URIs and web origins for the new domain.
    """
    if file_path is None:
        # Default to the file in services/keycloak/import relative to the project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.normpath(os.path.join(script_dir, "..", "services", "keycloak", "import", "digitaltwins-realm.json"))

    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    print(f"Patching {file_path} with target host: {target_host}")
    
    with open(file_path, "r") as f:
        data = json.load(f)

    # Iterate over all clients configured in the realm
    for client in data.get("clients", []):
        client_id = client.get("clientId")
        
        # 1. Update redirectUris
        redirect_uris = client.get("redirectUris", [])
        new_redirects = []
        for uri in redirect_uris:
            new_redirects.append(uri)
            
            # Most platform services (api, portal-frontend, airflow, minio, jupyterhub, orthanc, grafana)
            # use standard paths under localhost. We translate these to the new target host.
            if uri.startswith("http://localhost/"):
                target_uri = uri.replace("http://localhost", target_host)
                if target_uri not in redirect_uris and target_uri not in new_redirects:
                    new_redirects.append(target_uri)
                    
            # SEEK is a special case because it runs on a specific port (8001/3000) locally
            # and gets mapped to the /seek path on the deployed target host.
            elif uri.startswith("http://localhost:"):
                if client_id == "seek" and "/users/auth/seek/callback" in uri:
                    target_uri = target_host + "/seek/users/auth/seek/callback"
                    if target_uri not in redirect_uris and target_uri not in new_redirects:
                        new_redirects.append(target_uri)
                
        # Remove duplicates while preserving order
        client["redirectUris"] = list(dict.fromkeys(new_redirects))
        
        # 2. Update webOrigins for CORS
        web_origins = client.get("webOrigins", [])
        new_origins = []
        for origin in web_origins:
            new_origins.append(origin)
            
            # If a client allows localhost CORS, add the target host as well
            if origin == "http://localhost":
                if target_host not in web_origins and target_host not in new_origins:
                    new_origins.append(target_host)
            elif origin == "http://localhost/":
                target_host_slash = target_host + "/"
                if target_host_slash not in web_origins and target_host_slash not in new_origins:
                    new_origins.append(target_host_slash)
        
        client["webOrigins"] = list(dict.fromkeys(new_origins))

    # Write the modified data back to the file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    print("Successfully patched digitaltwins-realm.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch Keycloak realm config with a new host URL.")
    parser.add_argument(
        "--host", 
        type=str, 
        required=True, 
        help="The target host URL (e.g., https://dev-digitaltwins.abi-ctt-ctp.cloud.edu.au)"
    )
    parser.add_argument(
        "--file", 
        type=str, 
        default=None,
        help="Path to the Keycloak realm json file (default: resolves to services/keycloak/import/digitaltwins-realm.json)"
    )
    
    args = parser.parse_args()
    patch_realm(args.host, args.file)
