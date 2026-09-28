# Quantification of frequency of electrical activity from electrode measurements
#   Individual frequency quantification
cwlVersion: v1.2
class: Workflow

inputs:
  selected_electrode_channels:
    type: File
  threshold:
    type: double
  approximate_burst_locations:
    type: File
  position_of_electrodes:
    type: File

outputs:
  filtered_electrode_channels_fig:
    type: File
    outputSource: paper_figure/filtered_electrode_channels_fig
  publication_figs:
    type: File[]
    outputSource: plotting_figures_for_publication/publication_figs

steps:
  # 1
  load_file_into_matlab_script:
    run:
      class: Operation
      inputs:
        selected_electrode_channels: File
      outputs:
        time: string
        data: File
        electrodes: File
        sample_frequency: File
    in:
      selected_electrode_channels: selected_electrode_channels
    out: [time, data, electrodes, sample_frequency]
  # 2
  respiration_filtering:
    run:
      class: Operation
      inputs:
        time: string
        data: File
        sample_frequency: File
      outputs:
        filtered_data: File
    in:
      time: load_file_into_matlab_script/time
      data: load_file_into_matlab_script/data
      sample_frequency: load_file_into_matlab_script/sample_frequency
    out: [filtered_data]

  # 3
  paper_figure:
    run:
      class: Operation
      inputs:
        filtered_data: File
      outputs:
        filtered_electrode_channels_fig: File
    in:
      filtered_data: respiration_filtering/filtered_data
    out: [filtered_electrode_channels_fig]

  # 4
  frequency_analysis:
    run:
      class: Operation
      inputs:
        filtered_data: File
      outputs:
        mean_dominant_high_frequency: double
        mean_dominant_low_frequency: double
        standard_deviations: double
    in:
      filtered_data: respiration_filtering/filtered_data
    out: [mean_dominant_high_frequency, mean_dominant_low_frequency, standard_deviations]

  # 5
  burst_duration:
    run:
      class: Operation
      inputs:
        filtered_data: File
        threshold: double
        approximate_burst_locations: File
      outputs:
        mean_burst_duration: double
        standard_deviations: double
    in:
      filtered_data: respiration_filtering/filtered_data
      threshold: threshold
      approximate_burst_locations: approximate_burst_locations
    out: [mean_burst_duration, standard_deviations]

  # 6
  propagation_speed:
    run:
      class: Operation
      inputs:
        filtered_data: File
        position_of_electrodes: File
      outputs:
        mean_propagation_velocity: double
        standard_deviations: double
    in:
      filtered_data: respiration_filtering/filtered_data
      position_of_electrodes: position_of_electrodes
    out: [mean_propagation_velocity, standard_deviations]

  # 7
  plotting_figures_for_publication:
    run:
      class: Operation
      inputs:
        filtered_data: File
        time: string
      outputs:
        mean_propagation_velocity: double
        standard_deviations: double
        publication_figs: File[]
    in:
      filtered_data: respiration_filtering/filtered_data
      time: load_file_into_matlab_script/time
    out: [mean_propagation_velocity, standard_deviations, publication_figs]
