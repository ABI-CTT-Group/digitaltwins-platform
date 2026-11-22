cwlVersion: v1.2
class: CommandLineTool

label: "Tool - download samples"

baseCommand: [python, tool_download_samples.py]

inputs:
  mri_nifti:
    type: File
    inputBinding:
      prefix: --mri_nifti
      position: 1

outputs:
  nifti:
    type: File
    outputBinding:
      glob: "*.txt"
