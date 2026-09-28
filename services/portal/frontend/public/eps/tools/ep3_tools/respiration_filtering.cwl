cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, respiration_filtering.py]
inputs:
  time:
    type:
      type: string
    inputBinding:
      position: 1
  data:
    type:
      type: File
    inputBinding:
      position: 2
  sample_frequency:
    type:
      type: File
    inputBinding:
      position: 3
outputs:
  filtered_data:
    type: File

stdout: output.txt
