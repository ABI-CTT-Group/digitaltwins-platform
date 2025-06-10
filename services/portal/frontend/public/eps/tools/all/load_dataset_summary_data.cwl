cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, Load_dataset_summary_data.py]
inputs:
  excel_file:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  summary_data:
    type: File

stdout: output.txt
