cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, plotting_figures_for_publication.py]
inputs:
  filtered_data:
    type:
      type: File
    inputBinding:
      position: 1
  time:
    type:
      type: string
    inputBinding:
      position: 2
outputs:
  mean_propagation_velocity:
    type: double
  standard_deviations:
    type: double
  publication_figs:
    type: File[]

stdout: output.txt
