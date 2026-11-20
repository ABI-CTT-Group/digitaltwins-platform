cwlVersion: v1.2
class: Workflow

label: "Workflow - Mock statistical analysis"

inputs:
  lesion_position_reports:
    type: Directory
    doc: measurements

outputs:
  statistics_summary:
    type: Directory
    doc: measurements
    outputSource: run_notebook/statistics_summary

steps:
  run_notebook:
    run: tool_mock_statistical_analysis.cwl
    in:
      lesion_position_reports: lesion_position_reports
    out: [statistics_summary]
