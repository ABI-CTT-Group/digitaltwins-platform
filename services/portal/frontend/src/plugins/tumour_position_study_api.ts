import http from "./http";
import { ITumourStudyAppDetails } from "@/models/apiTypes";

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