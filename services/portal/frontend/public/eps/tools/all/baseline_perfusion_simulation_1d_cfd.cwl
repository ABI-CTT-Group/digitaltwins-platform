cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, baseline_perfusion_simulation_1d_cfd.py]
inputs:
  patient_config_file_csv:
    type:
      type: File
    inputBinding:
      position: 1
  1d_personalised_full_arterial_mesh_ip_format:
    type:
      type: File
    inputBinding:
      position: 2
outputs:
  baseline_arterial_tree_flow_field_ex_format:
    type: File
  baseline_pressure_field_ex_format:
    type: File
  baseline_radii_field_ex_format:
    type: File
  baseline_arterial_tree_terminal_flow_pressure_ex_format:
    type: File


stdout: output.txt
