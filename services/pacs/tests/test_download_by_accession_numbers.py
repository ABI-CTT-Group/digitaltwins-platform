import os
import sys
import requests
import argparse
import zipfile

# Configuration for source dt_pacs_2
ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8017")
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

def find_study(headers, accession_number):
    query = {
        "Level": "Study",
        "Query": {
            "AccessionNumber": accession_number
        }
    }
    response = requests.post(f"{ORTHANC_URL}/tools/find", json=query, headers=headers)
    response.raise_for_status()
    return response.json()

def download_study_archive(headers, study_id, accession_number, output_dir=None, unzip=True):
    print(f"Downloading archive for study {study_id} (Accession: {accession_number})...")
    response = requests.get(f"{ORTHANC_URL}/studies/{study_id}/archive", headers=headers, stream=True)
    response.raise_for_status()
    
    output_filename = f"study_{accession_number}_{study_id}.zip"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
    else:
        output_path = os.path.join(os.getcwd(), output_filename)
    
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                
    print(f"Successfully downloaded to {output_path}")
    
    if unzip:
        extract_dir = output_path[:-4] if output_path.endswith('.zip') else output_path + "_extracted"
        print(f"Unzipping to {extract_dir}...")
        with zipfile.ZipFile(output_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("Unzip complete.")
        os.remove(output_path)
        print(f"Deleted zip file: {output_path}")

def download_by_accession_numbers(accession_numbers, output_dir=None, unzip=True):
    print("Obtaining Keycloak token...")
    token = get_keycloak_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    for acc_num in accession_numbers:
        print(f"\n{'='*50}\nProcessing Accession Number: {acc_num}\n{'='*50}")
        print(f"Searching for study with AccessionNumber: {acc_num} in {ORTHANC_URL}...")
        
        try:
            study_ids = find_study(headers, acc_num)
            
            if not study_ids:
                print(f"No studies found with Accession Number: {acc_num}")
                continue
                
            print(f"Found {len(study_ids)} studies.")
            for study_id in study_ids:
                download_study_archive(headers, study_id, acc_num, output_dir, unzip)
                
        except Exception as e:
            print(f"Error processing {acc_num}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Download DICOM studies from Orthanc by Accession Number.")
    parser.add_argument("accession_numbers", nargs="*", default=["ACC-2024-00123"],
                        help="List of accession numbers to download. Defaults to ACC-2024-00123 if none provided.")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="Output directory for downloaded studies. Defaults to current working directory.")
    parser.add_argument("--unzip", action="store_true", default=True,
                        help="Unzip the downloaded studies (default: True).")
    parser.add_argument("--no-unzip", action="store_false", dest="unzip",
                        help="Do not unzip the downloaded studies.")
    args = parser.parse_args()
    
    download_by_accession_numbers(args.accession_numbers, args.output_dir, args.unzip)

if __name__ == "__main__":
    main()
