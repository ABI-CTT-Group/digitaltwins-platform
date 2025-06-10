cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, run_remodelling_disease.py]
inputs:
  flow_comparison_log_file:
    type:
      type: File
    inputBinding:
      position: 1
  1d_personalised_full_arterial_mesh_ip_format:
    type:
      type: File
    inputBinding:
      position: 2
  patient_config_file_csv:
    type:
      type: File
    inputBinding:
      position: 3
outputs:
  remodelling_burden:
    type: File

stdout: output.txt
