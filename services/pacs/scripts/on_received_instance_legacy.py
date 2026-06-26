"""
Orthanc Python Plugin: Automatic DICOM De-Identification on Receive

Intercepts all incoming DICOM instances and applies HIPAA Safe Harbor
de-identification before they reach persistent storage. The original
identified data is NEVER written to disk — only the de-identified version
is stored.

Approach: RegisterReceivedInstanceCallback (Python plugin >= 4.0)
Reference: DICOM PS 3.15 - Basic Application Level Confidentiality Profile
           https://www.dicomstandard.org/standards/view/security-and-privacy

On de-identification failure, the instance is DISCARDED (not stored).
This prevents PHI from leaking into storage. Check Orthanc logs for errors.
"""

import orthanc
from io import BytesIO
from pydicom import dcmread, dcmwrite
from pydicom.filebase import DicomFileLike


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Tags to KEEP despite the HIPAA profile normally removing them.
# These are clinically important and do not directly identify patients.
TAGS_TO_KEEP = {
    (0x0010, 0x1010),  # Patient's Age
    (0x0010, 0x1030),  # Patient's Weight
    (0x0010, 0x1020),  # Patient's Size
}

# Remove manufacturer-specific private tags (recommended for HIPAA compliance).
DELETE_PRIVATE_TAGS = True


# ---------------------------------------------------------------------------
# HIPAA Safe Harbor: Tags to blank
# Based on DICOM PS 3.15 Table E.1-1 (Basic Application Level Confidentiality)
# ---------------------------------------------------------------------------

TAGS_TO_EMPTY = {
    # Patient identifiers
    (0x0010, 0x0010),  # Patient's Name
    (0x0010, 0x0020),  # Patient ID
    (0x0010, 0x0030),  # Patient's Birth Date
    (0x0010, 0x0040),  # Patient's Sex
    (0x0010, 0x1000),  # Other Patient IDs
    (0x0010, 0x1001),  # Other Patient Names
    (0x0010, 0x2160),  # Ethnic Group
    (0x0010, 0x4000),  # Patient Comments
    (0x0010, 0x21B0),  # Additional Patient History

    # Study / institution identifiers
    (0x0008, 0x0050),  # Accession Number
    (0x0008, 0x0080),  # Institution Name
    (0x0008, 0x0081),  # Institution Address
    (0x0008, 0x0090),  # Referring Physician's Name
    (0x0008, 0x0092),  # Referring Physician's Address
    (0x0008, 0x0094),  # Referring Physician's Telephone
    (0x0008, 0x1048),  # Physician(s) of Record
    (0x0008, 0x1049),  # Physician(s) of Record Identification Sequence
    (0x0008, 0x1050),  # Performing Physician's Name
    (0x0008, 0x1060),  # Name of Physician(s) Reading Study
    (0x0008, 0x1070),  # Operators' Name

    # Dates and times (identifiable per HIPAA Safe Harbor)
    (0x0008, 0x0020),  # Study Date
    (0x0008, 0x0021),  # Series Date
    (0x0008, 0x0022),  # Acquisition Date
    (0x0008, 0x0023),  # Content Date
    (0x0008, 0x0030),  # Study Time
    (0x0008, 0x0031),  # Series Time
    (0x0008, 0x0032),  # Acquisition Time
    (0x0008, 0x0033),  # Content Time

    # Device / location identifiers
    (0x0008, 0x1010),  # Station Name
    (0x0008, 0x1040),  # Institutional Department Name
    (0x0008, 0x1030),  # Study Description (may contain free-text PHI)
    (0x0020, 0x0010),  # Study ID

    # Workflow / request identifiers
    (0x0032, 0x1032),  # Requesting Physician
    (0x0040, 0x0006),  # Scheduled Performing Physician's Name
    (0x0040, 0x0244),  # Performed Procedure Step Start Date
    (0x0040, 0x0245),  # Performed Procedure Step Start Time
    (0x0040, 0x0253),  # Performed Procedure Step ID
    (0x0040, 0x1001),  # Requested Procedure ID
}

# Structural DICOM UIDs required for a valid DICOM file — never blank these.
STRUCTURAL_TAGS = {
    (0x0008, 0x0016),  # SOP Class UID
    (0x0008, 0x0018),  # SOP Instance UID
    (0x0020, 0x000D),  # Study Instance UID
    (0x0020, 0x000E),  # Series Instance UID
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_dataset_to_bytes(dataset):
    """Serialize a pydicom Dataset to raw DICOM bytes."""
    with BytesIO() as buffer:
        memory_dataset = DicomFileLike(buffer)
        dcmwrite(memory_dataset, dataset)
        memory_dataset.seek(0)
        return memory_dataset.read()


def deidentify_dataset(dataset):
    """
    Apply HIPAA Safe Harbor de-identification to a pydicom Dataset in-place.

    - Blanks all tags listed in TAGS_TO_EMPTY
    - Skips tags in TAGS_TO_KEEP and STRUCTURAL_TAGS
    - Optionally removes all private (vendor) tags
    """
    for tag in TAGS_TO_EMPTY:
        if tag in TAGS_TO_KEEP or tag in STRUCTURAL_TAGS:
            continue
        if tag in dataset:
            dataset[tag].value = ""

    if DELETE_PRIVATE_TAGS:
        dataset.remove_private_tags()

    return dataset


# ---------------------------------------------------------------------------
# Orthanc Callback
# ---------------------------------------------------------------------------

def ReceivedInstanceCallback(receivedDicom, origin):
    """
    Invoked by Orthanc for every incoming DICOM instance before storage.

    Returns:
        (MODIFY, de-identified_bytes)  on success — only clean data is stored
        (DISCARD, None)                on failure — instance rejected, error logged
    """
    try:
        dataset = dcmread(BytesIO(receivedDicom))
        deidentify_dataset(dataset)

        orthanc.LogWarning(
            "[de-id] De-identified instance SOP=%s" % str(dataset.SOPInstanceUID)
        )

        return orthanc.ReceivedInstanceAction.MODIFY, write_dataset_to_bytes(dataset)

    except Exception as e:
        orthanc.LogError(
            "[de-id] FAILED — discarding instance to prevent PHI storage: %s" % str(e)
        )
        return orthanc.ReceivedInstanceAction.DISCARD, None


orthanc.RegisterReceivedInstanceCallback(ReceivedInstanceCallback)
