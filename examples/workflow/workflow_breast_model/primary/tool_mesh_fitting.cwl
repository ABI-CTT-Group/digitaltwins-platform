cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mesh fitting"

baseCommand: [python, tool_mesh_fitting.py]

inputs:
  point_cloud:
    type: File
    inputBinding:
      prefix: --point_cloud
      position: 1

outputs:
  breast_mesh:
    type: File
    outputBinding:
      glob: "*.txt"
