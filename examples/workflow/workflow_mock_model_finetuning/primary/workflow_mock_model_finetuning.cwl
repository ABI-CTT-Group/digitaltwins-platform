cwlVersion: v1.2
class: Workflow

label: "Workflow - Mock model fine-tuning"

inputs:
  clinician_validated_masks:
    type: Directory
    doc: measurements
  pretrained_models:
    type: Directory
    doc: models

outputs:
  finetuned_models:
    type: Directory
    doc: measurements
    outputSource: run_notebook/finetuned_models

steps:
  run_notebook:
    run: tool_mock_model_finetuning.cwl
    in:
      clinician_validated_masks: clinician_validated_masks
      pretrained_models: pretrained_models
    out: [finetuned_models]
