cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock statistical analysis"

baseCommand: ["jupyter", "notebook", "mock_statistical_analysis.ipynb"]

inputs:
  lesion_position_reports:
    type: Directory
    inputBinding:
      prefix: --lesion_position_reports
      position: 1

outputs:
  statistics_summary:
    type: Directory
    outputBinding:
      glob: "datasets/statistics_summary"
