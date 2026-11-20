cwlVersion: v1.2
class: CommandLineTool

label: "Tool - mock model fine-tuning"

baseCommand: ["jupyter", "notebook", "mock_model_finetuning.ipynb"]

inputs:
  clinician_validated_masks:
    type: Directory
    inputBinding:
      prefix: --clinician_validated_masks
      position: 1
  pretrained_models:
    type: Directory
    inputBinding:
      prefix: --pretrained_models
      position: 2

outputs:
  finetuned_models:
    type: Directory
    outputBinding:
      glob: "datasets/finetuned_models"
