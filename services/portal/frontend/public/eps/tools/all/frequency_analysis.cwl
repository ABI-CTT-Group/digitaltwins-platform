cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, frequency_analysis.py]
inputs:
  filtered_data:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  mean_dominant_high_frequency:
    type: double
  mean_dominant_low_frequency:
    type: double
  standard_deviations:
    type: double

stdout: output.txt
