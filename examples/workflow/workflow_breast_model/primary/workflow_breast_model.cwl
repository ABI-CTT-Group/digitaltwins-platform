cwlVersion: v1.2
class: Workflow

label: "Workflow - Generate breast model"

inputs:
  skin_inference_nifti:
    type: File
    doc: measurements
  outer_rib_inference_nifti:
    type: File
    doc: measurements
  sternum_inference_nifti:
    type: File
    doc: measurements

outputs:
  point_cloud:
    type: File
    outputSource: point_cloud_generation/point_cloud
    doc: measurements
  breast_mesh:
    type: File
    outputSource: mesh_fitting/breast_mesh
    doc: measurements

steps:
  point_cloud_generation:
    run: tool_point_cloud_generation.cwl
    in:
      skin_inference_nifti: skin_inference_nifti
      outer_rib_inference_nifti: outer_rib_inference_nifti
      sternum_inference_nifti: sternum_inference_nifti
    out: [point_cloud]
  mesh_fitting:
    run: tool_mesh_fitting.cwl
    in:
      point_cloud: point_cloud_generation/point_cloud
    out: [breast_mesh]
