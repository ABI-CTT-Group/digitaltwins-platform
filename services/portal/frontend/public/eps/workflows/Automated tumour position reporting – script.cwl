# Automated tumour position reporting – script
cwlVersion: v1.2
class: Workflow

inputs:
  mesh:
    type: File
  nipple_points:
    type: File
  tumour_centre:
    type: File
outputs:
  tumour_skin_distance:
    type: double
    outputSource: tumour_position_reporting/tumour_skin_distance
  tumour_rib_distance:
    type: double
    outputSource: tumour_position_reporting/tumour_rib_distance
  tumour_nipple_distance:
    type: double
    outputSource: tumour_position_reporting/tumour_nipple_distance
  clock_time:
    type: string
    outputSource: tumour_position_reporting/clock_time
  tumour_quadrant:
    type: string
    outputSource: tumour_position_reporting/tumour_quadrant

steps:
  tumour_position_reporting:
    run:
      class: Operation
      inputs:
        mesh: File
        nipple_points: File
        tumour_centre: File
      outputs:
        tumour_skin_distance: double
        tumour_rib_distance: double
        tumour_nipple_distance: double
        clock_time: string
        tumour_quadrant: string
    in:
      mesh: mesh
      nipple_points: nipple_points
      tumour_centre: tumour_centre
    out: [tumour_skin_distance, tumour_rib_distance, tumour_nipple_distance, clock_time, tumour_quadrant]
