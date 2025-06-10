cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, open_gems_and_load_experiment_file.py]
inputs:
  bdm_file:
    type:
      type: File
    inputBinding:
      position: 1
  experiment_records:
    type:
      type: File[]
    inputBinding:
      position: 2
  electrode_layout:
    type:
      type: File
    inputBinding:
      position: 3
  photos:
    type:
      type: File[]
    inputBinding:
      position: 4
outputs:
  selected_electrode_channels:
    type: File

stdout: output.txt
