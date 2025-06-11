# Generate personalised anatomical model of lung
cwlVersion: v1.2
class: Workflow


inputs:
  lobe_ply_meshes:
    type: Directory
  masked_mha_image:
    type: File
  mpa_segmentations:
    type: Directory

outputs:
  1d_personalised_full_arterial_mesh_ip_format:
    type: File
    outputSource: convert_ex_to_ip_ex2ip/1d_personalised_full_arterial_mesh_ip_format
  annotations_txt:
    type: File
    outputSource: centreline_annotation/upper_artery_1d_mesh_ip_format
  clusters:
    type: Directory
    outputSource: intensity_mapping_and_clustering/clusters

steps:
  #1
  create_seed_points:
    run:
      class: Operation
      inputs:
        lobe_ply_meshes: Directory
      outputs:
        lobe_datapoints: Directory
        lobe_surface_cmiss_files_ex_format: Directory
    in:
      lobe_ply_meshes: lobe_ply_meshes
    out: [lobe_datapoints, lobe_surface_cmiss_files_ex_format]
  #2
  intensity_mapping_and_clustering:
    run:
      class: Operation
      inputs:
        lobe_datapoints: Directory
        lobe_ply_meshes: Directory
        masked_mha_image: File
      outputs:
        clusters: Directory
    in:
      lobe_datapoints: create_seed_points/lobe_datapoints
      lobe_ply_meshes: lobe_ply_meshes
      masked_mha_image: masked_mha_image
    out: [clusters]
  #3
  centreline_annotation:
    run:
      class: Operation
      inputs:
        mpa_segmentations: Directory
        clusters: Directory
        lobe_ply_meshes: Directory
      outputs:
        upper_artery_1d_mesh_ip_format: File
        annotations_txt: File
    in:
      mpa_segmentations: mpa_segmentations
      clusters: intensity_mapping_and_clustering/clusters
      lobe_ply_meshes: lobe_ply_meshes
    out: [upper_artery_1d_mesh_ip_format, annotations_txt]
  #4
  grow_into_clusters:
    run:
      class: Operation
      inputs:
        lobe_ply_meshes: Directory
        upper_artery_1d_mesh_ip_format: File
        annotations_txt: File
      outputs:
        1d_personalised_full_arterial_mesh_ex_format: File
    in:
      lobe_ply_meshes: lobe_ply_meshes
      upper_artery_1d_mesh_ip_format: centreline_annotation/upper_artery_1d_mesh_ip_format
      annotations_txt: centreline_annotation/annotations_txt
    out: [1d_personalised_full_arterial_mesh_ex_format]
  #5
  convert_ex_to_ip_ex2ip:
    run:
      class: Operation
      inputs:
        1d_personalised_full_arterial_mesh_ex_format: File
      outputs:
        1d_personalised_full_arterial_mesh_ip_format: File
    in:
      1d_personalised_full_arterial_mesh_ex_format: grow_into_clusters/1d_personalised_full_arterial_mesh_ex_format
    out: [1d_personalised_full_arterial_mesh_ip_format]
