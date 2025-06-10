#Statistical analysis of electrode measurements
cwlVersion: v1.2
class: Workflow

inputs:
  excel_file:
    type: File

outputs:
  summary_stats_figure:
    type: File
    outputSource: plot_summary_statistics/summary_stats_figure

steps:
  # 1
  Load_dataset_summary_data:
    run:
      class: Operation
      inputs:
        excel_file: File
      outputs:
        summary_data: File
    in:
      excel_file: excel_file
    out: [summary_data]

  # 2
  plot_summary_statistics:
    run:
      class: Operation
      inputs:
        summary_data: File
      outputs:
        summary_stats_figure: File
    in:
      summary_data: Load_dataset_summary_data/summary_data
    out: [summary_stats_figure]
