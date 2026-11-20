cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock skin inference"

baseCommand: [python, tool_mock_skin_inference.py]

inputs:
  nifti:
    type: File
    inputBinding:
      prefix: --nifti
      position: 1
  skin_model:
    type: Directory
    inputBinding:
      prefix: --skin_model
      position: 2

outputs:
  skin_inference_nifti:
    type: File
    outputBinding:
      glob: "*.txt"
