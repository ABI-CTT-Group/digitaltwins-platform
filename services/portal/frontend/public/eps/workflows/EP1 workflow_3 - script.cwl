# Identify remodelling level to match pre-surgical PAP
cwlVersion: v1.2
class: Workflow


inputs:
  flow_comparison_log_file:
    type: File
  1d_personalised_full_arterial_mesh_ip_format:
    type: File
  patient_config_file_csv:
    type: File

outputs:
  remodelling_burden:
    type: File
    outputSource: run_remodelling_disease/remodelling_burden

steps:
  run_remodelling_disease:
    run:
      class: Operation
      inputs:
        flow_comparison_log_file: File
        1d_personalised_full_arterial_mesh_ip_format: File
        patient_config_file_csv: File
      outputs:
        remodelling_burden: File
    in:
      flow_comparison_log_file: flow_comparison_log_file
      1d_personalised_full_arterial_mesh_ip_format: 1d_personalised_full_arterial_mesh_ip_format
      patient_config_file_csv: patient_config_file_csv
    out: [remodelling_burden]
