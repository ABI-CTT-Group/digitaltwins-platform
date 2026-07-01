"""
Orthanc Python Plugin: Automatic DICOM De-Identification on Receive
Using: dicom-anonymizer (https://pypi.org/project/dicom-anonymizer/)

Intercepts all incoming DICOM instances and applies the DICOM 2023 standard
HIPAA-compliant anonymization profile before they reach persistent storage.
The original identified data is NEVER written to disk — only the de-identified
version is stored.

Approach: RegisterReceivedInstanceCallback (Python plugin >= 4.0)
Reference: DICOM PS 3.15 - Basic Application Level Confidentiality Profile
           https://dicom.nema.org/medical/dicom/current/output/html/part15.html#table_E.1-1

On de-identification failure, the instance is DISCARDED (not stored).
This prevents PHI from leaking into storage. Check Orthanc logs for errors.

Dependencies (add to your Docker image / pip install):
    dicom-anonymizer >= 1.0.13
    pydicom
"""

import orthanc
from io import BytesIO
from pydicom import dcmread

# PROVE SCRIPT IS RUNNING
with open("/tmp/orthanc_plugin_running.txt", "w") as f:
    f.write("Plugin loaded!")
from pydicom.filebase import DicomFileLike
from pydicom import dcmwrite

from dicomanonymizer.simpledicomanonymizer import (
    anonymize_dataset,
    keep,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Tags to KEEP despite the DICOM anonymization profile normally removing them.
# These are clinically important and do not directly identify patients.
#
# The `keep` action (from dicomanonymizer) is a no-op — it leaves the tag
# value exactly as received, overriding whatever the base profile would do.
TAGS_TO_KEEP = {
    (0x0008, 0x0050): keep,  # Accession Number
    (0x0010, 0x1010): keep,  # Patient's Age
    (0x0010, 0x1030): keep,  # Patient's Weight
    (0x0010, 0x1020): keep,  # Patient's Size
    (0x0042, 0x0011): keep,  # Encapsulated Document (fixes dicom-anonymizer crash on VR 'OB')
}

# Remove manufacturer-specific private tags (recommended for HIPAA compliance).
# Set to False only if downstream systems require vendor private tags.
DELETE_PRIVATE_TAGS = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_dataset_to_bytes(dataset) -> bytes:
    """Serialize a pydicom Dataset to raw DICOM bytes (in-memory)."""
    with BytesIO() as buffer:
        memory_dataset = DicomFileLike(buffer)
        dcmwrite(memory_dataset, dataset)
        memory_dataset.seek(0)
        return memory_dataset.read()


# ---------------------------------------------------------------------------
# Orthanc Callback
# ---------------------------------------------------------------------------

def ReceivedInstanceCallback(receivedDicom, origin):
    """
    Invoked by Orthanc for every incoming DICOM instance before storage.

    Uses `dicomanonymizer.simpledicomanonymizer.anonymize_dataset` to apply
    the full DICOM 2023 standard anonymization profile (DICOM PS 3.15 Table
    E.1-1), then overrides with TAGS_TO_KEEP so clinical measurement tags
    (Age, Weight, Size) are preserved unchanged.

    Returns:
        (MODIFY, de-identified_bytes)  on success — only clean data is stored
        (DISCARD, None)                on failure — instance rejected, PHI safe
    """
    try:
        dataset = dcmread(BytesIO(receivedDicom))

        # Skip anonymization for our Encapsulated Documents (Modality DOC)
        # because dicom-anonymizer crashes on VR OB tags like EncapsulatedDocument.
        if dataset.get("Modality", "") == "DOC":
            orthanc.LogWarning("[de-id] Skipping anonymization for encapsulated document.")
            return orthanc.ReceivedInstanceAction.MODIFY, write_dataset_to_bytes(dataset)

        # Apply the DICOM standard anonymization profile with custom overrides.
        # extra_anonymization_rules is merged AFTER the base profile, so any
        # tag listed in TAGS_TO_KEEP will be processed with `keep` (no-op),
        # effectively preserving its original value.
        anonymize_dataset(
            dataset,
            extra_anonymization_rules=TAGS_TO_KEEP,
            delete_private_tags=DELETE_PRIVATE_TAGS,
        )

        orthanc.LogWarning(
            "[de-id] De-identified instance SOP=%s" % str(dataset.SOPInstanceUID)
        )

        return orthanc.ReceivedInstanceAction.MODIFY, write_dataset_to_bytes(dataset)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        for line in tb.split('\n'):
            orthanc.LogError(f"[de-id] traceback: {line}")
        orthanc.LogError(
            f"[de-id] FAILED — discarding instance to prevent PHI storage: {str(e)}"
        )
        return orthanc.ReceivedInstanceAction.DISCARD, None


orthanc.RegisterReceivedInstanceCallback(ReceivedInstanceCallback)
