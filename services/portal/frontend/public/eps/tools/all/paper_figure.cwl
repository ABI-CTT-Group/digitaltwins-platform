cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, paper_figure.py]
inputs:
  filtered_data:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  filtered_electrode_channels_fig:
    type: File

stdout: output.txt
