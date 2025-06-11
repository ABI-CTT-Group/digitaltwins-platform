# Quantify scapulothoracic and glenohumeral posture in normal subjects
cwlVersion: v1.2
class: Workflow

inputs:
  surface_mesh_ply_scapula:
    type: File
  surface_mesh_ply_humerus:
    type: File
  surface_mesh_ply_clavicle:
    type: File
  surface_mesh_ply_thorax:
    type: File

outputs:
  clinical_measurements_csv:
    type: File
    outputSource: extract_clinical_measurements/clinical_measurements_csv

steps:
  extract_clinical_measurements:
    run:
      class: Operation
      inputs:
        surface_mesh_ply_scapula: File
        surface_mesh_ply_humerus: File
        surface_mesh_ply_clavicle: File
        surface_mesh_ply_thorax: File
      outputs:
        clinical_measurements_csv: File
    in:
      surface_mesh_ply_scapula: surface_mesh_ply_scapula
      surface_mesh_ply_humerus: surface_mesh_ply_humerus
      surface_mesh_ply_clavicle: surface_mesh_ply_clavicle
      surface_mesh_ply_thorax: surface_mesh_ply_thorax
    out: [clinical_measurements_csv]

