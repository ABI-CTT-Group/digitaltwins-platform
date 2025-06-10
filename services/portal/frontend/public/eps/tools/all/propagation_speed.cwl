cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, propagation_speed.py]
inputs:
  filtered_data:
    type:
      type: File
    inputBinding:
      position: 1
  position_of_electrodes:
    type:
      type: File
    inputBinding:
      position: 2
outputs:
  mean_propagation_velocity:
    type: double
  standard_deviations:
    type: double

stdout: output.txt
