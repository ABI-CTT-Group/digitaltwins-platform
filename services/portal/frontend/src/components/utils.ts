import * as Copper from "copper3d";

type TTumourCenter = { x: number; y: number; z: number; }

export const setTumourPosition = (nrrdTools: Copper.NrrdTools, center:TTumourCenter)=>{
    const spacing = nrrdTools.nrrd_states.voxelSpacing
    // Note: the tumour center we recieve is in mm, we need to convert it to (pixel, pixel, mm) in Axial view
    // pixel / spacing = mm
    // mm * spacing = pixel
    nrrdTools.setCalculateDistanceSphere(center.x * spacing[0], center.y * spacing[1], center.z, "tumour");
}