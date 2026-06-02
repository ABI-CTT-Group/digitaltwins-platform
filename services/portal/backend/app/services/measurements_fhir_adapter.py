"""Subclasses that bridge two gaps in the upstream ``fhir_cda`` library
for the measurements upload flow (plan 07).

Both subclasses are deliberately tiny — we want every difference vs upstream
in one place so a future patch / library upgrade is a 5-minute diff. The
intent is to file these upstream eventually; until then they live here.

S1: filename
----------------
``MeasurementAnnotator`` hard-codes its category to ``"measurements"``, and
the abstract base writes ``<root>/<category>.json`` on save. The portal
standardises on ``fhir.json`` so workflows / processes / measurements all
emit the same filename. ``MeasurementsFhirAnnotator`` flips that one
attribute and handles the round-trip dance in update mode (library reads
``measurements.json``, so we rename in then rename out).

S2: .nii (without .gz) support
------------------
``ImagingStudyMeasurement._read_sam`` only globs ``*.nii.gz``; a sample
folder containing a bare ``test.nii`` is silently dropped. The classifier
treats both as ImagingStudy, so the annotator must too. ``NiiCompatibleImagingStudy``
extends the glob and falls through to the upstream implementation for
DCM/NRRD/NII.GZ cases unchanged.
"""
from __future__ import annotations

from pathlib import Path

from fhir_cda.annotator.measurement_annotator import MeasurementAnnotator
from fhir_cda.ehr import ImagingStudyMeasurement
from fhir_cda.ehr.elements import ImagingStudySeries


class MeasurementsFhirAnnotator(MeasurementAnnotator):
    """Override upstream's hardcoded ``measurements.json`` to write/read ``fhir.json``.

    In default mode this is trivial: set ``_category = "fhir"`` after the
    base class has used the "measurements" category for its own analysis,
    so ``save()`` ends up at ``fhir.json``.

    In update mode the base class reads ``measurements.json`` at the top of
    ``__init__``. We can't subclass that read, so we temporarily rename
    ``fhir.json -> measurements.json`` before super().__init__ and clean up
    the temp file after. The net effect: caller never sees ``measurements.json``
    on disk; only ``fhir.json`` exists at rest.
    """

    def __init__(self, dataset_path, mode: str = "default"):
        dataset_root = Path(dataset_path)
        fhir_path = dataset_root / "fhir.json"
        mm_path = dataset_root / "measurements.json"

        # update mode: library expects measurements.json — rename in.
        renamed_for_update = False
        if mode == "update" and fhir_path.exists() and not mm_path.exists():
            fhir_path.rename(mm_path)
            renamed_for_update = True

        try:
            super().__init__(dataset_path, mode)
        finally:
            # Clean up either the temp rename (update mode) or any stray
            # measurements.json the library wrote during default-mode init.
            if renamed_for_update and mm_path.exists():
                # If anything blew up during super().__init__ we still want
                # fhir.json back to its original spot.
                mm_path.rename(fhir_path)

        # Flip the category so save() writes fhir.json from this point on.
        self._category = "fhir"


class NiiCompatibleImagingStudy(ImagingStudyMeasurement):
    """Extend upstream's ``_read_sam`` to recognise bare ``*.nii`` files.

    Upstream globs ``*.nii.gz`` only, so a sample folder containing
    ``something.nii`` is treated as empty and the series is dropped. Plan 07
    classifies both extensions as ImagingStudy candidates, so this subclass
    keeps them consistent.

    Behaviour:
      - Pure DCM / NRRD / NII.GZ sample → delegate to super() unchanged.
      - Pure bare .nii sample → build an ImagingStudySeries with the same
        shape upstream uses for NRRD (uid=None, no instances, count = number of nii).
      - Mixed (e.g. dcm + nii) → raise ValueError, same posture as upstream.
    """

    def _read_sam(self, sam):
        try:
            sample_path: Path = sam["path"]
            dcm_files = list(sample_path.glob("*.dcm"))
            nrrd_files = list(sample_path.glob("*.nrrd"))
            niigz_files = list(sample_path.glob("*.nii.gz"))
            # Exclude *.nii.gz from the bare-nii bucket — Path.glob("*.nii")
            # already matches .nii but not .nii.gz, so this is belt + braces.
            nii_files = [
                p for p in sample_path.glob("*.nii") if not p.name.endswith(".nii.gz")
            ]

            buckets = [
                bucket
                for bucket in (dcm_files, nrrd_files, niigz_files, nii_files)
                if bucket
            ]
            if not buckets:
                return None
            if len(buckets) > 1:
                raise ValueError(
                    "dataset format error: mixed imaging types in sample folder "
                    f"{sample_path.name} (found combinations of dcm/nrrd/nii/nii.gz)."
                )

            # Anything upstream already handles? Delegate.
            if dcm_files or nrrd_files or niigz_files:
                return super()._read_sam(sam)

            # Pure bare-.nii branch — same shape as upstream's nrrd/nii.gz output.
            return ImagingStudySeries(
                uid=None,
                endpoint_url="",
                endpoint_uuid=sam["uuid"],
                name=sample_path.name,
                number_of_instances=len(nii_files),
                instances=[],
            )
        except Exception as e:
            # Mirror upstream's swallow-and-log posture so the calling
            # _generate_imaging_study loop can move on to other samples.
            print(f"Error reading {sam}: {e}")
            return None
