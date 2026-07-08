"""
generate_test_dicom.py — Create a synthetic DICOM file containing known PHI
for use in de-identification tests.

The file is populated with recognizable fake values across all HIPAA-sensitive
fields, plus the three tags that must survive de-identification:
  - Patient's Age  (0010,1010)  → "041Y"
  - Patient's Weight (0010,1030) → "75.5"
  - Patient's Size   (0010,1020) → "1.78"

Output: tests/testdata/synthetic_phi.dcm

Usage:
    python tests/generate_test_dicom.py
"""

import os
import pydicom
from pydicom.dataset import FileDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian
import pydicom.uid
import numpy as np
import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "testdata")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "synthetic_phi.dcm")


def create_synthetic_dicom():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- File meta -----------------------------------------------------------
    file_meta = pydicom.Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    file_meta.ImplementationVersionName = "TEST_GENERATOR_1.0"

    ds = FileDataset(OUTPUT_FILE, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    # --- SOP Common (structural — must survive) -------------------------------
    ds.SOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()

    # --- HIPAA-sensitive fields (all should be blanked after de-id) ----------

    # Patient identification
    ds.PatientName = "DOE^JOHN^MICHAEL"
    ds.PatientID = "TEST-PAT-001"
    ds.PatientBirthDate = "19850115"
    ds.PatientSex = "M"
    ds.OtherPatientIDs = "ALT-ID-999"
    ds.EthnicGroup = "NOT HISPANIC OR LATINO"
    ds.PatientComments = "Test patient — do not use in production"
    ds.AdditionalPatientHistory = "No relevant history"

    # Institution identifiers
    ds.AccessionNumber = "ACC-2026-00002"
    ds.InstitutionName = "Springfield General Hospital"
    ds.InstitutionAddress = "123 Main Street, Springfield, IL 62701"
    ds.ReferringPhysicianName = "DR^SMITH^JAMES"
    ds.PerformingPhysicianName = "DR^JONES^EMILY"
    ds.OperatorsName = "TECH^OPERATOR^A"

    # Dates and times
    now = datetime.datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.SeriesDate = now.strftime("%Y%m%d")
    ds.AcquisitionDate = now.strftime("%Y%m%d")
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.SeriesTime = now.strftime("%H%M%S")
    ds.AcquisitionTime = now.strftime("%H%M%S")
    ds.ContentTime = now.strftime("%H%M%S")

    # Device/location identifiers
    ds.StationName = "MR-SCANNER-01"
    ds.InstitutionalDepartmentName = "Radiology"
    ds.StudyDescription = "BRAIN MRI WITH CONTRAST"
    ds.StudyID = "STU-2024-001"

    # --- Tags that MUST be preserved after de-identification -----------------
    ds.PatientAge = "041Y"     # (0010,1010) Patient's Age
    ds.PatientWeight = 75.5    # (0010,1030) Patient's Weight (in kg)
    ds.PatientSize = 1.78      # (0010,1020) Patient's Size (height in m)

    # --- Image module (minimal valid SC image) --------------------------------
    ds.Modality = "MR"
    ds.SeriesNumber = "1"
    ds.InstanceNumber = "1"
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 8
    ds.Columns = 8
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0

    # Synthetic 8x8 gradient pixel array
    pixel_array = np.arange(64, dtype=np.uint8).reshape((8, 8))
    ds.PixelData = pixel_array.tobytes()

    pydicom.dcmwrite(OUTPUT_FILE, ds)
    print(f"[OK] Synthetic DICOM created: {OUTPUT_FILE}")
    print(f"     PatientName   = {ds.PatientName}")
    print(f"     PatientID     = {ds.PatientID}")
    print(f"     PatientAge    = {ds.PatientAge}  ← should SURVIVE de-id")
    print(f"     PatientWeight = {ds.PatientWeight}  ← should SURVIVE de-id")
    print(f"     PatientSize   = {ds.PatientSize}  ← should SURVIVE de-id")
    return OUTPUT_FILE


if __name__ == "__main__":
    create_synthetic_dicom()
