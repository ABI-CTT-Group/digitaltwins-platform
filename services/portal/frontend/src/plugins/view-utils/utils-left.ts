import { IRequests, IDetails } from "@/models/apiTypes";
import {  ITumourStudyAppDetail } from "@/models/apiTypes";

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


export function customRound(num:number) {
  const decimalPart = num - Math.floor(num);
  
  if (decimalPart > 0.5) {
    return Math.ceil(num);  
  } else {
    return Math.floor(num); 
  }
}

export function distance3D(x1:number, y1:number, z1:number, x2:number, y2:number, z2:number) {
  let dx = x2 - x1;
  let dy = y2 - y1;
  let dz = z2 - z1;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

export const getReportIncompleteCases = (
  details: Array<ITumourStudyAppDetail>
):ITumourStudyAppDetail[] => {
  return details.filter((item) => item.report.complete === false);
};

export const getTumourCenterInCompleteCases = (
  details: Array<ITumourStudyAppDetail>
):ITumourStudyAppDetail[] => {
  return details.filter((item) => item.tumour_window.validate === false);
};

export const getTumourAssitedInCompleteCases = (
  details: Array<ITumourStudyAppDetail>
):ITumourStudyAppDetail[] => {
  return details.filter((item) => item.report.assisted === false && item.report.complete === true);
};