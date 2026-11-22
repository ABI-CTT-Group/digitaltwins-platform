cwlVersion: v1.2
class: Workflow

label: "Workflow - Inference"

inputs:
  mri_nifti:
    type: File
    doc: measurements
  skin_model:
    type: Directory
    doc: models
  outer_rib_model:
    type: Directory
    doc: models
  sternum_model:
    type: Directory
    doc: models
  lesion_model:
    type: Directory
    doc: models

outputs:
  skin_inference_nifti:
    type: File
    outputSource: skin_inference/skin_inference_nifti
    doc: measurements
  outer_rib_inference_nifti:
    type: File
    outputSource: outer_rib_inference/outer_rib_inference_nifti
    doc: measurements
  sternum_inference_nifti:
    type: File
    outputSource: sternum_inference/sternum_inference_nifti
    doc: measurements
  lesion_inference_nifti:
    type: File
    outputSource: lesion_inference/lesion_inference_nifti
    doc: measurements

steps:
  download_samples:
    run: tool_download_samples.cwl
    in:
      mri_nifti: mri_nifti
    out: [nifti]
  skin_inference:
    run: tool_skin_inference.cwl
    in:
      nifti: download_samples/nifti
      skin_model: skin_model
    out: [skin_inference_nifti]
  outer_rib_inference:
    run: tool_outer_rib_inference.cwl
    in:
      nifti: download_samples/nifti
      outer_rib_model: outer_rib_model
    out: [outer_rib_inference_nifti]
  sternum_inference:
    run: tool_sternum_inference.cwl
    in:
      nifti: download_samples/nifti
      sternum_model: sternum_model
    out: [sternum_inference_nifti]
  lesion_inference:
    run: tool_lesion_inference.cwl
    in:
      nifti: download_samples/nifti
      lesion_model: lesion_model
    out: [lesion_inference_nifti]
