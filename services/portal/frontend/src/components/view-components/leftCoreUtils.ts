import * as Copper from "copper3d";

export const switchAnimationStatus = (loadingContainer:HTMLDivElement, progress:HTMLDivElement, status: "flex" | "none", text?: string) => {
    loadingContainer!.style.display = status;
    !!text && (progress!.innerText = text);
};

export function addNameToLoadedMeshes( nrrdMesh: Copper.nrrdMeshesType, name: string) {
    nrrdMesh.x.name = name + " sagittal";
    nrrdMesh.y.name = name + " coronal";
    nrrdMesh.z.name = name + " axial";
}