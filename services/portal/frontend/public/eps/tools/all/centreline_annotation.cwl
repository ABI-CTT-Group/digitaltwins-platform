cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, centreline_annotation.py]
inputs:
  mpa_segmentations:
    type:
      type: Directory
    inputBinding:
      position: 1
  clusters:
    type:
      type: Directory
    inputBinding:
      position: 2
  lobe_ply_meshes:
    type:
      type: Directory
    inputBinding:
      position: 3
outputs:
  upper_artery_1d_mesh_ip_format:
    type: File
  annotations_txt:
    type: File

stdout: output.txt
