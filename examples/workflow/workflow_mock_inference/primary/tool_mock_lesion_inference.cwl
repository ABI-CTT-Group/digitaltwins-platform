cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock lesion inference"

baseCommand: [python, tool_mock_lesion_inference.py]

inputs:
  nifti:
    type: File
    inputBinding:
      prefix: --nifti
      position: 1
  lesion_model:
    type: Directory
    inputBinding:
      prefix: --lesion_model
      position: 2

outputs:
  lesion_inference_nifti:
    type: File
    outputBinding:
      glob: "*.txt"
