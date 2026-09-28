cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, load_file_into_matlab_script.py]
inputs:
  selected_electrode_channels:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  time:
    type: string
  data:
    type: File
  electrodes:
    type: File
  sample_frequency:
    type: File

stdout: output.txt
