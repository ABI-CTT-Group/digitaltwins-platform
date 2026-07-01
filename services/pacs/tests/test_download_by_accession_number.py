# pip install pydicom pynetdicom

import os
import sys
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove
)

# Configuration for source orthanc-1
ORTHANC_IP = "127.0.0.1"
ORTHANC_PORT = 8015  # DICOM port from .env (ORTHANC_1_DICOM_PORT=8015)
ORTHANC_AET = b"dt_pacs_1"  # AET from .env (ORTHANC_1_AET=dt_pacs_1)

# Our SCU Application Entity Title
OUR_AET = b"TEST_SCU"

# Target PACS Application Entity Title (Orthanc 2)
TARGET_PACS_AET = b"dt_pacs_2"

# Target Accession Number
TARGET_ACCESSION_NUMBER = "ACC-2024-00123"

def main():
    print(f"Starting DICOM test script using C-MOVE...")
    print(f"Source Orthanc: {ORTHANC_IP}:{ORTHANC_PORT} (AET: {ORTHANC_AET.decode()})")
    print(f"Destination PACS AET: {TARGET_PACS_AET.decode()}")
    print(f"Searching for Accession Number: {TARGET_ACCESSION_NUMBER}")

    # Initialize SCU Application Entity
    scu_ae = AE(ae_title=OUR_AET)
    scu_ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
    scu_ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)

    print(f"Connecting to Source Orthanc for C-FIND...")
    assoc = scu_ae.associate(ORTHANC_IP, ORTHANC_PORT, ae_title=ORTHANC_AET)

    if not assoc.is_established:
        print("Failed to establish association. Check Orthanc is running and DICOM port is exposed.")
        sys.exit(1)

    print("Association established successfully.")

    # 1. C-FIND to get Study Instance UID
    print(f"\n--- 1. C-FIND ---")

    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.AccessionNumber = TARGET_ACCESSION_NUMBER
    ds.StudyInstanceUID = ''
    ds.PatientID = ''
    ds.PatientName = ''

    study_uids = []

    print("Sending C-FIND request...")
    responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)

    for (status, identifier) in responses:
        if status:
            if identifier:
                study_uid = identifier.StudyInstanceUID
                study_uids.append(study_uid)
                print(f"  Found Study:")
                print(f"    StudyInstanceUID: {study_uid}")
                print(f"    PatientID: {getattr(identifier, 'PatientID', 'Unknown')}")
                print(f"    PatientName: {getattr(identifier, 'PatientName', 'Unknown')}")
        else:
            print("Connection timed out, was aborted or received invalid response")

    assoc.release()

    if not study_uids:
        print("No studies found with the given Accession Number.")
        sys.exit(0)

    # 2. C-MOVE to request transfer to Target PACS
    print(f"\n--- 2. C-MOVE ---")
    
    assoc_move = scu_ae.associate(ORTHANC_IP, ORTHANC_PORT, ae_title=ORTHANC_AET)

    if not assoc_move.is_established:
        print("Failed to establish association for C-MOVE.")
        sys.exit(1)

    for study_uid in study_uids:
        print(f"Sending C-MOVE request for Study UID: {study_uid} to destination {TARGET_PACS_AET.decode()}...")

        move_ds = Dataset()
        move_ds.QueryRetrieveLevel = 'STUDY'
        move_ds.StudyInstanceUID = study_uid

        # Send C-MOVE with target AET
        responses = assoc_move.send_c_move(move_ds, TARGET_PACS_AET, StudyRootQueryRetrieveInformationModelMove)

        for (status, identifier) in responses:
            if status:
                if status.Status != 0x0000 and status.Status != 0xFF00: # not success and not pending
                    print(f"C-MOVE status: 0x{status.Status:04x}")
                elif status.Status == 0x0000:
                    print(f"C-MOVE for Study UID {study_uid} completed successfully.")
            else:
                print("Connection timed out, was aborted or received invalid response")

    assoc_move.release()
    print(f"\nAssociation released. C-MOVE operation finished.")

if __name__ == "__main__":
    main()

