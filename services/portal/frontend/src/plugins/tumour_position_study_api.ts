import http from "./http";
import { ITumourStudyAppDetails, ITumourStudyReport, ITumourStudyAssisted } from "@/models/apiTypes";

export interface ITumourStudyReportExtent extends ITumourStudyReport {
  case_name: string;
}

export async function useTumourPositionStudyDetails() {
    const details = http.get<ITumourStudyAppDetails>("/tumour_position");
    return details;
}

export async function useStudyDisplayNrrd(filepath: string) {
    return new Promise((resolve, reject) => {
      http
        .getBlob("/tumour_position/display", { filepath })
        .then((data) => {
          const nrrdUrl = URL.createObjectURL(new Blob([data as BlobPart]));
          resolve(nrrdUrl);
        })
        .catch((error) => {
          reject(error);
        });
    });
}

export async function useSaveTumourStudyReport(body: ITumourStudyReportExtent) {
  const success = http.post<boolean>("/tumour_position/report", body);
  return success;
}

export async function useSaveTumourPositionAssisted(body: ITumourStudyAssisted) {
  const success = http.post<boolean>("/tumour_position/assisted", body);
  return success;
}