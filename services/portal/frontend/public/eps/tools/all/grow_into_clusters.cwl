cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, grow_into_clusters.py]
inputs:
  lobe_ply_meshes:
    type:
      type: Directory
    inputBinding:
      position: 1
  upper_artery_1d_mesh_ip_format:
    type:
      type: File
    inputBinding:
      position: 2
  annotations_txt:
    type:
      type: File
    inputBinding:
      position: 3
outputs:
  1d_personalised_full_arterial_mesh_ex_format:
    type: File

stdout: output.txt
