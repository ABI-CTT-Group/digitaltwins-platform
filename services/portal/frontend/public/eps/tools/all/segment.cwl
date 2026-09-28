cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, segment.py]
inputs:
  nifti:
    type:
      type: File
    inputBinding:
      position: 1
  seg_model_lung:
    type:
      type: Directory
    inputBinding:
      position: 2
  seg_model_skin:
    type:
      type: Directory
    inputBinding:
      position: 3
outputs:
  segmentation_lung:
    type: File
    outputBinding:
      glob: "*.nii"
  segmentation_skin:
    type: File
    outputBinding:
      glob: "*.nii"
  nipple_points:
    type: File

stdout: output.txt
