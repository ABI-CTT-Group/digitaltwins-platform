cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, flow_intensity_analysis_and_comparison_to_baseline.py]
inputs:
  annotations_txt:
    type:
      type: File
    inputBinding:
      position: 1
  baseline_arterial_tree_flow_field_ex_format:
    type:
      type: File
    inputBinding:
      position: 2
  baseline_pressure_field_ex_format:
    type:
      type: File
    inputBinding:
      position: 3
  baseline_radii_field_ex_format:
    type:
      type: File
    inputBinding:
      position: 4
  baseline_arterial_tree_terminal_flow_pressure_ex_format:
    type:
      type: File
    inputBinding:
      position: 5
  clusters:
    type:
      type: Directory
    inputBinding:
      position: 6
outputs:
  flow_comparison_log_file:
    type: File


stdout: output.txt
