cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, burst_duration.py]
inputs:
  filtered_data:
    type:
      type: File
    inputBinding:
      position: 1
  threshold:
    type:
      type: double
    inputBinding:
      position: 2
  approximate_burst_locations:
    type:
      type: File
    inputBinding:
      position: 3
outputs:
  mean_burst_duration:
    type: double
  standard_deviations:
    type: double

stdout: output.txt
