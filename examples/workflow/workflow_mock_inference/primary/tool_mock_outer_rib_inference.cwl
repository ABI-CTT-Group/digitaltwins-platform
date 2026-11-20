cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock outer rib inference"

baseCommand: [python, tool_mock_outer_rib_inference.py]

inputs:
  nifti:
    type: File
    inputBinding:
      prefix: --nifti
      position: 1
  outer_rib_model:
    type: Directory
    inputBinding:
      prefix: --outer_rib_model
      position: 2

outputs:
  outer_rib_inference_nifti:
    type: File
    outputBinding:
      glob: "*.txt"
