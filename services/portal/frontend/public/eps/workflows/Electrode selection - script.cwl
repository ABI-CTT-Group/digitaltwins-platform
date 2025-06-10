# Electrode selection
cwlVersion: v1.2
class: Workflow


inputs:
  bdm_file:
    type: File
  experiment_records:
    type: File[]
  electrode_layout:
    type: File
  photos:
    type: File[]

outputs:
  selected_electrode_channels:
    type: File
    outputSource: open_gems_and_load_experiment_file/selected_electrode_channels

steps:
  # uGEM software data segmentation
  # Break down into small chunks – baby steps through each analysis step
  open_gems_and_load_experiment_file:
    run:
      class: Operation
      inputs:
        bdm_file: File
        experiment_records: File[]
        electrode_layout: File
        photos: File[]
      outputs:
        selected_electrode_channels: File
    in:
      bdm_file: bdm_file
      experiment_records: experiment_records
      electrode_layout: electrode_layout
      photos: photos
    out: [selected_electrode_channels]
