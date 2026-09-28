cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, run_post_pea_prediction.py]
inputs:
  1d_personalised_full_arterial_mesh_ip_format:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  pressure_prediction:
    type: File

stdout: output.txt
