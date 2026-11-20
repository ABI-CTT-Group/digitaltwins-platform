cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock sternum inference"

baseCommand: [python, tool_mock_sternum_inference.py]

inputs:
  nifti:
    type: File
    inputBinding:
      prefix: --nifti
      position: 1
  sternum_model:
    type: Directory
    inputBinding:
      prefix: --sternum_model
      position: 2

outputs:
  sternum_inference_nifti:
    type: File
    outputBinding:
      glob: "*.txt"
