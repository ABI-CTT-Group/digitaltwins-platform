# Predict post surgery PAP (after removing occlusions)
cwlVersion: v1.2
class: Workflow


inputs:
  1d_personalised_full_arterial_mesh_ip_format:
    type: File

outputs:
  pressure_prediction:
    type: File
    outputSource: run_post_pea_prediction/pressure_prediction

steps:
  run_post_pea_prediction:
    run:
      class: Operation
      inputs:
        1d_personalised_full_arterial_mesh_ip_format: File
      outputs:
        pressure_prediction: File
    in:
      1d_personalised_full_arterial_mesh_ip_format: 1d_personalised_full_arterial_mesh_ip_format
    out: [pressure_prediction]
