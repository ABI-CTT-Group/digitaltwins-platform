import os
import sys
import argparse
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8014")
ORTHANC_USER = os.environ.get("ORTHANC_USER", "admin")
ORTHANC_PASSWORD = os.environ.get("ORTHANC_PASSWORD", "admin")
AUTH = (ORTHANC_USER, ORTHANC_PASSWORD)

def upload_dicom(file_path):
    """Upload a DICOM file to Orthanc and return the instance ID."""
    print(f"Uploading '{file_path}' to Orthanc at {ORTHANC_URL}...")
    
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)
        
    with open(file_path, "rb") as f:
        data = f.read()
        
    try:
        response = requests.post(
            f"{ORTHANC_URL}/instances", 
            data=data, 
            auth=AUTH,
            headers={"Content-Type": "application/dicom"}, 
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        instance_id = result.get("ID")
        status = result.get("Status", "Unknown")
        
        print(f"[SUCCESS] Upload complete.")
        print(f"  - Instance ID: {instance_id}")
        print(f"  - Status:      {status}")
        
        return instance_id
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to upload DICOM: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  - Server Response: {e.response.text}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Test uploading a DICOM file to Orthanc.")
    parser.add_argument(
        "dicom_file", 
        nargs="?", 
        default=os.path.join(os.path.dirname(__file__), "testdata", "synthetic_phi.dcm"),
        help="Path to the DICOM file to upload"
    )
    
    args = parser.parse_args()
    upload_dicom(args.dicom_file)

if __name__ == "__main__":
    main()
