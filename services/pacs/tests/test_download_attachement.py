import os
import io
import sys
import requests
import pydicom

ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8014")
KEYCLOAK_TOKEN_URL = os.environ.get("KEYCLOAK_TOKEN_URL", "http://localhost:8009/realms/digitaltwins/protocol/openid-connect/token")
ORTHANC_USER = os.environ.get("ORTHANC_USER", "admin")
ORTHANC_PASSWORD = os.environ.get("ORTHANC_PASSWORD", "admin")

def get_keycloak_token():
    try:
        response = requests.post(
            KEYCLOAK_TOKEN_URL,
            data={
                "client_id": "orthanc",
                "username": ORTHANC_USER,
                "password": ORTHANC_PASSWORD,
                "grant_type": "password"
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"[ERROR] Failed to obtain Keycloak token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Keycloak Response: {e.response.text}")
        sys.exit(1)

def find_instances(headers, patient_id):
    query = {
        "Level": "Instance",
        "Query": {
            "PatientID": patient_id
        }
    }
    response = requests.post(f"{ORTHANC_URL}/tools/find", json=query, headers=headers)
    response.raise_for_status()
    return response.json()

def download_and_extract(headers, instance_id):
    response = requests.get(f"{ORTHANC_URL}/instances/{instance_id}/file", headers=headers)
    response.raise_for_status()
    
    ds = pydicom.dcmread(io.BytesIO(response.content))
    
    if hasattr(ds, 'MIMETypeOfEncapsulatedDocument') and ds.MIMETypeOfEncapsulatedDocument == "text/plain":
        if hasattr(ds, 'EncapsulatedDocument'):
            print(f"Found Accession Numbers in Instance ID: {instance_id}")
            content = ds.EncapsulatedDocument.decode('utf-8')
            print("--- Contents ---")
            print(content)
            print("----------------")
            
            output_path = "./downloaded_accession_numbers.txt"
            with open(output_path, "wb") as f:
                f.write(ds.EncapsulatedDocument)
            print(f"Saved locally to {output_path}")
            return True
    return False

def main():
    print("Obtaining Keycloak token...")
    token = get_keycloak_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    patient_id = "DUMMY-DICOM-ENCAPS"
    
    print(f"Searching for instances with PatientID: {patient_id}...")
    instances = find_instances(headers, patient_id)
    print(f"Found {len(instances)} instances.")
    
    found = False
    for instance_id in instances:
        if download_and_extract(headers, instance_id):
            found = True
            
    if not found:
        print("Could not find any text/plain encapsulated document for the given Patient ID.")

if __name__ == "__main__":
    main()
