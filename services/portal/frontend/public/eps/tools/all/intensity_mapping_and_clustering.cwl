cwlVersion: v1.2
class: CommandLineTool
baseCommand: [python, intensity_mapping_and_clustering.py]
inputs:
  lobe_datapoints:
    type:
      type: Directory
    inputBinding:
      position: 1
  lobe_ply_meshes:
    type:
      type: Directory
    inputBinding:
      position: 2
  masked_mha_image:
    type:
      type: File
    inputBinding:
      position: 3
outputs:
  clusters:
    type: Directory

stdout: output.txt
