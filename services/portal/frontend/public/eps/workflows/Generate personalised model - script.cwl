# Generate personalised model
cwlVersion: v1.2
class: Workflow

inputs:
  sternum_mesh:
    type: File
  ribs_mesh:
    type: File
  template_mesh_scapula:
    type: File
  template_mesh_humerus:
    type: File
  template_mesh_clavicle:
    type: File
  template_mesh_thorax:
    type: File
  surface_mesh_stl_scapula:
    type: File
  surface_mesh_stl_humerus:
    type: File
  surface_mesh_stl_clavicle:
    type: File

outputs:
  surface_mesh_ply_scapula:
    type: File
    outputSource: mesh_fitting/surface_mesh_ply_scapula
  surface_mesh_ply_humerus:
    type: File
    outputSource: mesh_fitting/surface_mesh_ply_humerus
  surface_mesh_ply_clavicle:
    type: File
    outputSource: mesh_fitting/surface_mesh_ply_clavicle
  surface_mesh_ply_thorax:
    type: File
    outputSource: mesh_fitting/surface_mesh_ply_thorax

steps:
  join_sternum_and_ribs:
    run:
      class: Operation
      inputs:
        sternum_mesh: File
        ribs_mesh: File
      outputs:
        thorax_mesh: File
    in:
      sternum_mesh: sternum_mesh
      ribs_mesh: ribs_mesh
    out: [thorax_mesh]

  mesh_fitting:
    run:
      class: Operation
      inputs:
        template_mesh_scapula: File
        template_mesh_humerus: File
        template_mesh_clavicle: File
        template_mesh_thorax: File
        surface_mesh_stl_scapula: File
        surface_mesh_stl_humerus: File
        surface_mesh_stl_clavicle: File
        surface_mesh_stl_thorax: File
      outputs:
        surface_mesh_ply_scapula: File
        surface_mesh_ply_humerus: File
        surface_mesh_ply_clavicle: File
        surface_mesh_ply_thorax: File
    in:
      template_mesh_scapula: template_mesh_scapula
      template_mesh_humerus: template_mesh_humerus
      template_mesh_clavicle: template_mesh_clavicle
      template_mesh_thorax: template_mesh_thorax
      surface_mesh_stl_scapula: surface_mesh_stl_scapula
      surface_mesh_stl_humerus: surface_mesh_stl_humerus
      surface_mesh_stl_clavicle: surface_mesh_stl_clavicle
      surface_mesh_stl_thorax: join_sternum_and_ribs/thorax_mesh
    out: [surface_mesh_ply_scapula,
          surface_mesh_ply_humerus,
          surface_mesh_ply_clavicle,
          surface_mesh_ply_thorax]


