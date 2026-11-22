# Model fine-tuning workflow

A notebook workflow that stands in for fine-tuning the skin, outer rib, sternum and lesion models on clinician-validated masks
in demos. Nothing is computed.

`code/model_finetuning.ipynb` has one cell per step (load annotations, fine-tune the skin model, fine-tune the outer rib model, fine-tune the sternum model, fine-tune the lesion model, export the models); each waits about
10 seconds. The last cell copies the input dataset to `outputs/datasets/` with a note
that it is a placeholder, so Submit uploads a dataset.

Register it like any workflow (see `docs/workflow-dag-authoring.md` in the platform repository);
the platform repository's breast pilot populate script (listed in `util/SCRIPTS.md`) registers all four
stand-in workflows and creates their assays.
