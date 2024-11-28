import * as Copper from "copper3d";
import { IRequests, IDetails } from "@/models/apiTypes";

export function addNameToLoadedMeshes(
  nrrdMesh: Copper.nrrdMeshesType,
  name: string
) {
  nrrdMesh.x.name = name + " sagittal";
  nrrdMesh.y.name = name + " coronal";
  nrrdMesh.z.name = name + " axial";
}

export const findRequestUrls = (
  details: Array<IDetails>,
  caseId: string,
  type: "registration" | "origin"
) => {
  const currentCaseDetails = details.filter((item) => item.name === caseId)[0];
  const requests: Array<IRequests> = [];
  if (type === "registration") {
    currentCaseDetails.file_paths.registration_nrrd_paths.forEach(
      (filepath) => {
        requests.push({
          url: "/single-file",
          params: { path: filepath },
        });
      }
    );
  } else if (type === "origin") {
    currentCaseDetails.file_paths.origin_nrrd_paths.forEach((filepath) => {
      requests.push({
        url: "/single-file",
        params: { path: filepath },
      });
    });
  }

  if (currentCaseDetails.masked) {
    currentCaseDetails.file_paths.segmentation_manual_mask_paths.forEach(
      (filepath) => {
        requests.push({
          url: "/single-file",
          params: { path: filepath },
        });
      }
    );
  }
  return requests;
};
