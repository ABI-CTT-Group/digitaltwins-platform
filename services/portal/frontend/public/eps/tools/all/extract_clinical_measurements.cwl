cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, join_sternum_and_ribs.py]
inputs:
  surface_mesh_ply_scapula:
    type:
      type: File
    inputBinding:
      position: 1
  surface_mesh_ply_humerus:
    type:
      type: File
    inputBinding:
      position: 2
  surface_mesh_ply_clavicle:
    type:
      type: File
    inputBinding:
      position: 1
  surface_mesh_ply_thorax:
    type:
      type: File
    inputBinding:
      position: 2
outputs:
  clinical_measurements_csv:
    type: File

stdout: output.txt
