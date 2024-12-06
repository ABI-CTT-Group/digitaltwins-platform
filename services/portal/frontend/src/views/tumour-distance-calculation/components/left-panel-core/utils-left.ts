import * as Copper from "copper3d";
import {  ITumourStudyAppDetail } from "@/models/apiTypes";

export function addNameToLoadedMeshes(
  nrrdMesh: Copper.nrrdMeshesType,
  name: string
) {
  nrrdMesh.x.name = name + " sagittal";
  nrrdMesh.y.name = name + " coronal";
  nrrdMesh.z.name = name + " axial";
}

export const getIncompleteCases = (
  details: Array<ITumourStudyAppDetail>
):ITumourStudyAppDetail[] => {
  return details.filter((item) => item.report.complete === false);
};
