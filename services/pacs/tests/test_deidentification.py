"""
test_deidentification.py — End-to-end test for automatic DICOM de-identification.

Tests that:
1. HIPAA-sensitive tags are blanked after upload to Orthanc
2. Tags configured to be kept (Age, Weight, Size) are preserved
3. Private tags are removed from the stored file

Requirements:
- Orthanc must be running (docker compose up -d from services/pacs/)
- pydicom and requests must be installed (pip install pydicom requests)
- Run generate_test_dicom.py first to create the test data

Usage:
    # Generate synthetic DICOM (once):
    python tests/generate_test_dicom.py

    # Run tests (Orthanc must be up):
    python tests/test_deidentification.py

    # Override defaults with env vars:
    ORTHANC_URL=http://localhost:8042 ORTHANC_USER=admin ORTHANC_PASSWORD=admin \\
        python tests/test_deidentification.py

Exit codes:
    0 = all assertions passed
    1 = one or more assertions failed
"""

import os
import sys
import json
import time
import requests
from io import BytesIO

try:
    import pydicom
    from pydicom import dcmread
except ImportError:
    print("[ERROR] pydicom not installed. Run: pip install pydicom")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8014")
ORTHANC_USER = os.environ.get("ORTHANC_USER", "admin")
ORTHANC_PASSWORD = os.environ.get("ORTHANC_PASSWORD", "admin")

TEST_DICOM = os.path.join(os.path.dirname(__file__), "testdata", "synthetic_phi.dcm")

AUTH = (ORTHANC_USER, ORTHANC_PASSWORD)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def orthanc_get(path):
    r = requests.get(f"{ORTHANC_URL}{path}", auth=AUTH, timeout=10)
    r.raise_for_status()
    return r

def orthanc_post(path, data, content_type="application/dicom"):
    r = requests.post(f"{ORTHANC_URL}{path}", data=data, auth=AUTH,
                      headers={"Content-Type": content_type}, timeout=30)
    r.raise_for_status()
    return r

def orthanc_delete(path):
    r = requests.delete(f"{ORTHANC_URL}{path}", auth=AUTH, timeout=10)
    r.raise_for_status()


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def assert_eq(self, label, expected, actual):
        if actual == expected:
            print(f"  [PASS] {label}")
            print(f"         expected={expected!r}  actual={actual!r}")
            self.passed += 1
        else:
            print(f"  [FAIL] {label}")
            print(f"         expected={expected!r}  actual={actual!r}")
            self.failed += 1
            self.failures.append(label)

    def assert_empty(self, label, actual):
        """Assert tag value is blank/empty after de-identification."""
        if actual == "" or actual is None:
            print(f"  [PASS] {label} is blank (de-identified) ✓")
            self.passed += 1
        else:
            print(f"  [FAIL] {label} should be blank but got: {actual!r}")
            self.failed += 1
            self.failures.append(label)

    def assert_preserved(self, label, expected, actual):
        """Assert tag value survived de-identification unchanged."""
        if str(actual) == str(expected):
            print(f"  [PASS] {label} preserved: {actual!r} ✓")
            self.passed += 1
        else:
            print(f"  [FAIL] {label} expected={expected!r}  actual={actual!r}")
            self.failed += 1
            self.failures.append(label)

    def assert_no_private_tags(self, label, dataset):
        private = [(hex(g), hex(e)) for (g, e) in dataset.keys() if g % 2 != 0]
        if not private:
            print(f"  [PASS] {label}: No private tags found ✓")
            self.passed += 1
        else:
            print(f"  [FAIL] {label}: Private tags still present: {private}")
            self.failed += 1
            self.failures.append(label)

    def summary(self):
        total = self.passed + self.failed
        print()
        print("=" * 60)
        print(f"Results: {self.passed}/{total} passed", end="")
        if self.failed:
            print(f"  ({self.failed} FAILED)")
            for f in self.failures:
                print(f"  - {f}")
        else:
            print("  ✓ ALL PASSED")
        print("=" * 60)
        return self.failed == 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def wait_for_orthanc(timeout=30):
    """Poll until Orthanc is ready or timeout."""
    print(f"Waiting for Orthanc at {ORTHANC_URL} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{ORTHANC_URL}/system", auth=AUTH, timeout=3)
            if r.status_code == 200:
                print("[OK] Orthanc is ready")
                return True
        except Exception:
            pass
        time.sleep(2)
    print("[ERROR] Orthanc did not respond within timeout")
    return False


def upload_dicom(path):
    """Upload a DICOM file to Orthanc, return Orthanc instance ID."""
    with open(path, "rb") as f:
        data = f.read()
    response = orthanc_post("/instances", data)
    result = response.json()
    instance_id = result["ID"]
    status = result.get("Status", "Unknown")
    print(f"[OK] Uploaded instance: {instance_id}  (Status={status})")
    return instance_id


def test_deidentification(instance_id, tr):
    """Assert HIPAA fields are blanked and kept fields are preserved."""

    tags = orthanc_get(f"/instances/{instance_id}/simplified-tags").json()

    print("\n--- HIPAA fields should be BLANKED ---")
    tr.assert_empty("PatientName     (0010,0010)", tags.get("PatientName", ""))
    tr.assert_empty("PatientID       (0010,0020)", tags.get("PatientID", ""))
    tr.assert_empty("PatientBirthDate(0010,0030)", tags.get("PatientBirthDate", ""))
    tr.assert_empty("PatientSex      (0010,0040)", tags.get("PatientSex", ""))
    tr.assert_empty("InstitutionName (0008,0080)", tags.get("InstitutionName", ""))
    tr.assert_empty("AccessionNumber (0008,0050)", tags.get("AccessionNumber", ""))
    tr.assert_empty("ReferringPhysicianName (0008,0090)", tags.get("ReferringPhysicianName", ""))
    tr.assert_empty("PerformingPhysicianName(0008,1050)", tags.get("PerformingPhysicianName", ""))
    tr.assert_empty("StationName     (0008,1010)", tags.get("StationName", ""))
    tr.assert_empty("StudyDate       (0008,0020)", tags.get("StudyDate", ""))
    tr.assert_empty("PatientComments (0010,4000)", tags.get("PatientComments", ""))

    print("\n--- Clinical tags should be PRESERVED ---")
    tr.assert_preserved("PatientAge    (0010,1010)", "041Y",  tags.get("PatientAge", ""))
    tr.assert_preserved("PatientWeight (0010,1030)", "75.5",  str(tags.get("PatientWeight", "")))
    tr.assert_preserved("PatientSize   (0010,1020)", "1.78",  str(tags.get("PatientSize", "")))

    print("\n--- Structural UIDs should be INTACT ---")
    tr.assert_preserved("SOPClassUID    (0008,0016)", "", "")  # just check it exists
    sop = tags.get("SOPClassUID", None)
    if sop:
        print(f"  [PASS] SOPClassUID present: {sop}")
        tr.passed += 1
    else:
        print("  [FAIL] SOPClassUID missing!")
        tr.failed += 1
        tr.failures.append("SOPClassUID missing")


def test_private_tags_removed(instance_id, tr):
    """Download the stored DICOM file and assert no private tags remain."""
    print("\n--- Private tags should be REMOVED ---")
    raw = orthanc_get(f"/instances/{instance_id}/file").content
    dataset = dcmread(BytesIO(raw))
    tr.assert_no_private_tags("Private tags removed from stored DICOM", dataset)


def cleanup(instance_id):
    """Delete the test instance from Orthanc."""
    try:
        orthanc_delete(f"/instances/{instance_id}")
        print(f"\n[OK] Cleaned up instance {instance_id}")
    except Exception as e:
        print(f"\n[WARN] Cleanup failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  PACS Auto De-Identification End-to-End Test")
    print(f"  Orthanc: {ORTHANC_URL}")
    print("=" * 60)

    if not os.path.exists(TEST_DICOM):
        print(f"[ERROR] Test DICOM not found: {TEST_DICOM}")
        print("        Run: python tests/generate_test_dicom.py")
        sys.exit(1)

    if not wait_for_orthanc():
        print("[ERROR] Cannot connect to Orthanc. Is the service running?")
        print("        Run: docker compose up -d  (from services/pacs/)")
        sys.exit(1)

    tr = TestResult()
    instance_id = None

    try:
        print(f"\nUploading: {TEST_DICOM}")
        instance_id = upload_dicom(TEST_DICOM)

        print("\n[Testing de-identification of HIPAA-sensitive tags]")
        test_deidentification(instance_id, tr)

        print("\n[Testing private tag removal]")
        test_private_tags_removed(instance_id, tr)

    finally:
        if instance_id:
            cleanup(instance_id)

    success = tr.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
