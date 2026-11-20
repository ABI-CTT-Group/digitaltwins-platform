cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock point cloud generation"

baseCommand: [python, tool_mock_point_cloud_generation.py]

inputs:
  skin_inference_nifti:
    type: File
    inputBinding:
      prefix: --skin_inference_nifti
      position: 1
  outer_rib_inference_nifti:
    type: File
    inputBinding:
      prefix: --outer_rib_inference_nifti
      position: 2
  sternum_inference_nifti:
    type: File
    inputBinding:
      prefix: --sternum_inference_nifti
      position: 3

outputs:
  point_cloud:
    type: File
    outputBinding:
      glob: "*.txt"
