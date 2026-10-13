cwlVersion: v1.2
class: CommandLineTool

label: "Tool - dicom to nifti"

requirements:
  DockerRequirement:
    dockerPull: python:3.12.3
  InitialWorkDirRequirement:
    listing:
      - entryname: run.sh
        entry: |-
          #!/bin/bash
          pip install dicom2nifti pydicom
          python tool_dicom_to_nifti.py "$@"
  InlineJavascriptRequirement: {}

baseCommand: [bash, run.sh]

inputs:
  dicom_input:
    type: Directory
    inputBinding:
      prefix: --input
      position: 1

outputs:
  rai_nifti_output:
    type: File
    outputBinding:
      glob: "*.nii.gz"
