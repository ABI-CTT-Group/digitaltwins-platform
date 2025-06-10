cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, create_point_cloud.py]
inputs:
  segmentation_lung:
    type:
      type: File
    inputBinding:
      position: 1
  segmentation_skin:
    type:
      type: File
    inputBinding:
      position: 2
outputs:
  point_cloud_lung:
    type: File
  point_cloud_skin:
    type: File

stdout: output.txt
