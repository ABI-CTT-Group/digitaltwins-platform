cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, create_mesh.py]
inputs:
  point_cloud_lung:
    type:
      type: File
    inputBinding:
      position: 1
  point_cloud_skin:
    type:
      type: File
    inputBinding:
      position: 2
  pca_model:
    type:
      type: Directory
    inputBinding:
      position: 3
outputs:
  mesh:
    type: File

stdout: output.txt
