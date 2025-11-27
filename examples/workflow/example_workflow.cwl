# Automated torso model generation – script

cwlVersion: v1.2

class: Workflow



inputs:

  dicom:

    type: Directory

  seg_model_lung:

    type: Directory

  seg_model_skin:

    type: Directory

  pca_model:

    type: Directory

outputs:

  nifti:

    type: File

    outputSource: create_nifti/nifti

  segmentation_lung:

    type: File

    outputSource: segment/segmentation_lung

  segmentation_skin:

    type: File

    outputSource: segment/segmentation_skin

  nipple_points:

    type: File

    outputSource: segment/nipple_points

  point_cloud_lung:

    type: File

    outputSource: create_point_cloud/point_cloud_lung

  point_cloud_skin:

    type: File

    outputSource: create_point_cloud/point_cloud_skin

  mesh:

    type: File

    outputSource: create_mesh/mesh



steps:

  create_nifti:

    run:

      class: Operation

      inputs:

        dicom: Directory

      outputs:

        nifti: File

    in:

      dicom: dicom

    out: [nifti]



  segment:

    run:

      class: Operation

      inputs:

        nifti: File

        seg_model_lung: Directory

        seg_model_skin: Directory

      outputs:

        segmentation_lung: File

        segmentation_skin: File

        nipple_points: File

    in:

      nifti: create_nifti/nifti

      seg_model_lung: seg_model_lung

      seg_model_skin: seg_model_skin

    out: [segmentation_lung, segmentation_skin, nipple_points]



  create_point_cloud:

    run:

      class: Operation

      inputs:

        segmentation_lung: File

        segmentation_skin: File

      outputs:

        point_cloud_lung: File

        point_cloud_skin: File

    in:

      segmentation_lung: segment/segmentation_lung

      segmentation_skin: segment/segmentation_skin

    out: [point_cloud_lung, point_cloud_skin]



  create_mesh:

    run:

      class: Operation

      inputs:

        point_cloud_lung: File

        point_cloud_skin: File

        pca_model: Directory

      outputs:

        mesh: File

    in:

      point_cloud_lung: create_point_cloud/point_cloud_lung

      point_cloud_skin: create_point_cloud/point_cloud_skin

      pca_model: pca_model

    out: [mesh]
