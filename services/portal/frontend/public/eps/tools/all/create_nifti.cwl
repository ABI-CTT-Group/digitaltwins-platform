cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, create_nifti.py]
inputs:
  dicom:
    type:
      type: Directory
    inputBinding:
      position: 1
outputs:
  nifti:
    type: File
    outputBinding:
      glob: "*.nii"

stdout: output.txt
