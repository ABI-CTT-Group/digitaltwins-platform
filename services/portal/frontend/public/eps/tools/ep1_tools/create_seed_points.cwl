cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, create_seed_points.py]
inputs:
  lobe_ply_meshes:
    type:
      type: Directory
    inputBinding:
      position: 1
outputs:
  lobe_datapoints:
    type: Directory
  lobe_surface_cmiss_files_ex_format:
    type: Directory

stdout: output.txt
