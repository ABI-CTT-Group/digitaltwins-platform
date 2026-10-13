cwlVersion: v1.2
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerPull: python:3.12.3
  InitialWorkDirRequirement:
    listing:
      - entryname: run.sh
        entry: |-
          #!/bin/bash
          pip install SimpleITK
          python tool_dicom_to_nrrd.py "$@"
  InlineJavascriptRequirement: {}

baseCommand: [bash, run.sh]

inputs:
  dicom_input:
    type: Directory
    inputBinding:
      prefix: --input
      position: 1

outputs:
  nrrd_output:
    type: File
    outputBinding:
      glob: "*.nrrd"
