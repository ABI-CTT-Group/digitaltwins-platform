import os
import sys
import io
import requests
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, RawDataStorage, ExplicitVRLittleEndian

# Configuration
ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8014")
KEYCLOAK_TOKEN_URL = os.environ.get("KEYCLOAK_TOKEN_URL", "http://localhost:8009/realms/digitaltwins/protocol/openid-connect/token")
ORTHANC_USER = os.environ.get("ORTHANC_USER", "admin")
ORTHANC_PASSWORD = os.environ.get("ORTHANC_PASSWORD", "admin")

DATA_DIR = os.path.join(os.path.dirname(__file__), "testdata")
CSV_PATH = os.path.join(DATA_DIR, "clinical_records.csv")
TXT_PATH = os.path.join(DATA_DIR, "accession_numbers")

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

def encapsulate_file(file_path, patient_id):
    """
    Wraps an arbitrary file into a DICOM RawDataStorage instance.
    """
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = RawDataStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.SOPClassUID = RawDataStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    
    ds.PatientID = patient_id
    ds.PatientName = "DUMMY^PATIENT"

    ds.Modality = "DOC"
    
    # Read the file
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    # Use standard DICOM EncapsulatedDocument tag
    if file_path.endswith(".csv"):
        ds.MIMETypeOfEncapsulatedDocument = "text/csv"
        ds.DocumentTitle = "Clinical Records"
    else:
        ds.MIMETypeOfEncapsulatedDocument = "text/plain"
        ds.DocumentTitle = "Accession Numbers"
        
    ds.EncapsulatedDocument = file_bytes

    return ds

def upload_dicom(ds, url, headers):
    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    dicom_bytes = buf.getvalue()

    response = requests.post(
        f"{url}/instances",
        data=dicom_bytes,
        headers=headers,
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def run_test():
    print("[1/5] Obtaining Keycloak token...")
    token = get_keycloak_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    dicom_headers = headers.copy()
    dicom_headers["Content-Type"] = "application/dicom"

    patient_id = "DUMMY-DICOM-ENCAPS"

    print("[2/5] Encapsulating and uploading clinical_records.csv...")
    try:
        ds_csv = encapsulate_file(CSV_PATH, patient_id)
        res_csv = upload_dicom(ds_csv, ORTHANC_URL, dicom_headers)
        csv_instance_id = res_csv["ID"]
        print(f"      ✓ Uploaded CSV as Instance ID: {csv_instance_id}")
    except Exception as e:
        print(f"[ERROR] Failed to upload CSV DICOM: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server Response: {e.response.text}")
        sys.exit(1)

    print("[3/5] Encapsulating and uploading accession_numbers...")
    try:
        ds_txt = encapsulate_file(TXT_PATH, patient_id)
        res_txt = upload_dicom(ds_txt, ORTHANC_URL, dicom_headers)
        txt_instance_id = res_txt["ID"]
        print(f"      ✓ Uploaded TXT as Instance ID: {txt_instance_id}")
    except Exception as e:
        print(f"[ERROR] Failed to upload TXT DICOM: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server Response: {e.response.text}")
        sys.exit(1)

    print("[4/5] Verifying stored instances...")
    try:
        # Download and verify CSV
        r_csv = requests.get(f"{ORTHANC_URL}/instances/{csv_instance_id}/file", headers=headers)
        r_csv.raise_for_status()
        ds_csv_down = pydicom.dcmread(io.BytesIO(r_csv.content))
        with open(CSV_PATH, "rb") as f:
            if ds_csv_down.EncapsulatedDocument != f.read():
                print("[ERROR] CSV content mismatch!")
                sys.exit(1)
        print("      clinicalRecords:   content matches ✓")
        print("      --- CSV Contents ---")
        print(ds_csv_down.EncapsulatedDocument.decode('utf-8'))
        print("      --------------------")
        
        # Save CSV locally
        csv_download_path = "downloaded_clinical_records.csv"
        with open(csv_download_path, "wb") as f:
            f.write(ds_csv_down.EncapsulatedDocument)
        print(f"      Saved CSV locally to {csv_download_path}")

        # Download and verify TXT
        r_txt = requests.get(f"{ORTHANC_URL}/instances/{txt_instance_id}/file", headers=headers)
        r_txt.raise_for_status()
        ds_txt_down = pydicom.dcmread(io.BytesIO(r_txt.content))
        with open(TXT_PATH, "rb") as f:
            if ds_txt_down.EncapsulatedDocument != f.read():
                print("[ERROR] TXT content mismatch!")
                sys.exit(1)
        print("      accessionNumbers:  content matches ✓")
        print("      --- TXT Contents ---")
        print(ds_txt_down.EncapsulatedDocument.decode('utf-8'))
        print("      --------------------")

        # Save TXT locally
        txt_download_path = "downloaded_accession_numbers.txt"
        with open(txt_download_path, "wb") as f:
            f.write(ds_txt_down.EncapsulatedDocument)
        print(f"      Saved TXT locally to {txt_download_path}")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        sys.exit(1)

    print("[5/5] Cleaning up test data...")
    try:
        r_patient = requests.get(f"{ORTHANC_URL}/instances/{csv_instance_id}/patient", headers=headers)
        orthanc_patient_id = r_patient.json()["ID"]
        requests.delete(f"{ORTHANC_URL}/patients/{orthanc_patient_id}", headers=headers)
        print("      ✓")
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {e}")
        sys.exit(1)

    print("\nAll tests passed.")

if __name__ == "__main__":
    run_test()
