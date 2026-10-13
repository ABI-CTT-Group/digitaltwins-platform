cwlVersion: v1.2
class: Workflow

label: "Workflow - Image conversion"

inputs:
  dicom_input:
    type: Directory
    doc: measurements

outputs:
  nifti_output:
    type: File
    outputSource: dicom_to_nifti/rai_nifti_output
    doc: measurements
  nrrd_output:
    type: File
    outputSource: dicom_to_nrrd/nrrd_output
    doc: measurements

steps:
  dicom_to_nifti:
    run: tool_dicom_to_nifti.cwl
    in:
      dicom_input: dicom_input
    out: [rai_nifti_output]

  dicom_to_nrrd:
    run: tool_dicom_to_nrrd.cwl
    in:
      dicom_input: dicom_input
    out: [nrrd_output]
