cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, plot_summary_statistics.py]
inputs:
  summary_data:
    type:
      type: File
    inputBinding:
      position: 1
outputs:
  summary_stats_figure:
    type: File

stdout: output.txt
