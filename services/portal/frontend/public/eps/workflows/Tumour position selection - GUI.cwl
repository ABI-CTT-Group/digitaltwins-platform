# Tumour position selection - GUI
cwlVersion: v1.2
class: Workflow

inputs:
  dicom:
    type: Directory
  mesh:
    type: File

outputs:
  tumour_centre:
    type: File
    outputSource: locate_tumour/tumour_centre

steps:
  locate_tumour:
    run:
      class: Operation
      inputs:
        dicom: Directory
        mesh: File
      outputs:
        tumour_centre: File
    in:
      dicom: dicom
      mesh: mesh
    out: [tumour_centre]
