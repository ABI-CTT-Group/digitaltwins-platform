# Identify under perfused regions
cwlVersion: v1.2
class: Workflow


inputs:
  patient_config_file_csv:
    type: File
  1d_personalised_full_arterial_mesh_ip_format:
    type: File
  annotations_txt:
    type: File
  clusters:
    type: Directory

outputs:
  flow_comparison_log_file:
    type: File
    outputSource: flow_intensity_analysis_and_comparison_to_baseline/flow_comparison_log_file

steps:
  baseline_perfusion_simulation_1d_cfd:
    run:
      class: Operation
      inputs:
        patient_config_file_csv: File
        1d_personalised_full_arterial_mesh_ip_format: File
      outputs:
        baseline_arterial_tree_flow_field_ex_format: File
        baseline_pressure_field_ex_format: File
        baseline_radii_field_ex_format: File
        baseline_arterial_tree_terminal_flow_pressure_ex_format: File
    in:
      patient_config_file_csv: patient_config_file_csv
      1d_personalised_full_arterial_mesh_ip_format: 1d_personalised_full_arterial_mesh_ip_format
    out: [baseline_arterial_tree_flow_field_ex_format,
          baseline_pressure_field_ex_format,
          baseline_radii_field_ex_format,
          baseline_arterial_tree_terminal_flow_pressure_ex_format]
  flow_intensity_analysis_and_comparison_to_baseline:
    run:
      class: Operation
      inputs:
        annotations_txt: File
        baseline_arterial_tree_flow_field_ex_format: File
        baseline_pressure_field_ex_format: File
        baseline_radii_field_ex_format: File
        baseline_arterial_tree_terminal_flow_pressure_ex_format: File
        clusters: Directory
      outputs:
        flow_comparison_log_file: File
    in:
      annotations_txt: patient_config_file_csv
      baseline_arterial_tree_flow_field_ex_format: baseline_perfusion_simulation_1d_cfd/baseline_arterial_tree_flow_field_ex_format
      baseline_pressure_field_ex_format: baseline_perfusion_simulation_1d_cfd/baseline_pressure_field_ex_format
      baseline_radii_field_ex_format: baseline_perfusion_simulation_1d_cfd/baseline_radii_field_ex_format
      baseline_arterial_tree_terminal_flow_pressure_ex_format: baseline_perfusion_simulation_1d_cfd/baseline_arterial_tree_terminal_flow_pressure_ex_format
      clusters: clusters
    out: [flow_comparison_log_file]

