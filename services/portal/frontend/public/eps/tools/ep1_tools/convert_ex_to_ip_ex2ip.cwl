cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, convert_ex_to_ip_ex2ip.py]
inputs:
  1d_personalised_full_arterial_mesh_ex_format:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  1d_personalised_full_arterial_mesh_ip_format:
    type: File

stdout: output.txt
