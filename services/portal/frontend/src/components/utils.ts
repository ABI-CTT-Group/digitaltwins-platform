import * as Copper from "copper3d";

type TTumourCenter = { x: number; y: number; z: number; }

export const setTumourStudyPointPosition = (
                                            nrrdTools: Copper.NrrdTools, 
                                            point:TTumourCenter, 
                                            status:"tumour"|"nipple"|"skin"|"ribcage")=>{
    const spacing = nrrdTools.nrrd_states.voxelSpacing
    // Note: the tumour center we recieve is in mm, we need to convert it to (pixel, pixel, mm) in Axial view
    // pixel / spacing = mm
    // mm * spacing = pixel
    nrrdTools.setCalculateDistanceSphere(point.x * spacing[0], point.y * spacing[1], point.z, status);
}

