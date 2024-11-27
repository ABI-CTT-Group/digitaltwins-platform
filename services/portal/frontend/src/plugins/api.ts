import http from "./http";
import {
  INrrdCaseNames,
  IExportMask,
  ICaseUrls,
  ICaseRegUrls,
  IExportMasks,
  IReplaceMask,
  ISaveSphere,
  IRegRquest,
  IRequests,
} from "@/models/apiTypes";
import JSZip from "jszip";
/**
 *
 * @returns Get all cases's names
 */
export async function useNrrdCaseNames() {
  const names = http.get<INrrdCaseNames>("/cases");
  return names;
}
/**
 *
 */
export async function useNrrdCaseFiles(requests: Array<IRequests>) {
  return new Promise<ICaseUrls>((resolve, reject) => {
    let urls: ICaseUrls = { nrrdUrls: [], jsonUrl: "" };
    http
      .all(requests)
      .then((files) => {
        (files as any[]).forEach((item) => {
          if (item.filename.includes(".json")) {
            urls.jsonUrl = URL.createObjectURL(item.data);
          } else {
            urls.nrrdUrls.push(URL.createObjectURL(item.data));
          }
        });
        resolve(urls);
      })
      .catch((error) => {
        reject(error);
      });
  });
}
/**
 *
 * @param name case name/id
 * @returns Get all nrrd files in the case folder
 */
export async function useNrrdCase(name: string): Promise<ICaseUrls> {
  return new Promise((resolve, reject) => {
    let urls: ICaseUrls = { nrrdUrls: [], jsonUrl: "" };
    http.getBlob("/case", { name }).then((zipBlob) => {
      const zip = new JSZip();
      // Extract the contents of the zip archive
      zip.loadAsync(zipBlob as any).then((contents) => {
        const nrrdNames = [];
        let jsonName = "";
        for (let prop in contents.files) {
          if (prop.includes(".nrrd")) {
            nrrdNames.push(prop);
          } else if (prop.includes(".json")) {
            jsonName = prop;
          }
        }
        const promises: any = [];
        nrrdNames.forEach((name) => {
          const file = contents.files[name];
          promises.push(file.async("arraybuffer"));
        });
        if (jsonName !== "") {
          const file = contents.files[jsonName];
          promises.push(file.async("arraybuffer"));
        }
        Promise.all(promises)
          .then((values) => {
            values.forEach((item, index) => {
              if (jsonName !== "" && index === values.length - 1) {
                urls.jsonUrl = URL.createObjectURL(new Blob([item]));
              } else {
                urls.nrrdUrls.push(URL.createObjectURL(new Blob([item])));
              }
            });
            resolve(urls);
          })
          .catch((err) => {
            reject(err);
          });
      });
    });
  });
}
/**
 * init the mask data in backend
 * @param body
 * @returns
 */
export async function useInitMasks(body: IExportMasks) {
  const success = http.post<boolean>("/mask/init", body);
  return success;
}
/**
 * replace the specific mask
 * @param body
 * @returns
 */
export async function useReplaceMask(body: IReplaceMask) {
  const success = http.post<boolean>("/mask/replace", body);
  return success;
}
/**
 * sava sphere origin and raduis in mm
 * @param body
 * @returns
 */
export async function useSaveSphere(body: ISaveSphere) {
  const success = http.post<boolean>("/sphere/save", body);
  return success;
}
/**
 * Save mask
 * @returns
 */
export async function useSaveMasks(name: string) {
  const success = http.get<boolean>("/mask/save", { name });
  return success;
}
export async function useMask(name: string) {
  return new Promise((resolve, reject) => {
    http
      .getBlob("/mask", { name })
      .then((data) => {
        const jsonUrl = URL.createObjectURL(
          new Blob([data as BlobPart], { type: "application/json" })
        );
        resolve(jsonUrl);
      })
      .catch((error) => {
        reject(error);
      });
  });
}
export async function useBreastPointsJson(name: string, filename:string) {
  return new Promise((resolve, reject) => {
    http
      .get("/breast_points", { name, filename })
      .then((data) => {
        resolve(data);
      })
      .catch((error) => {
        reject(error);
      });
  });
}
export async function useMaskNrrd(name: string) {
  return new Promise((resolve, reject) => {
    http
      .getBlob("/display", { name })
      .then((data) => {
        const maskNrrdUrl = URL.createObjectURL(new Blob([data as BlobPart]));
        resolve(maskNrrdUrl);
      })
      .catch((error) => {
        reject(error);
      });
  });
}
export async function useMaskObjMesh(name: string) {
  return new Promise((resolve, reject) => {
    http
      .getBlob("/mesh", { name })
      .then((res) => {
        
        if(res === 404){
          resolve(false);
        }else{
          const maskMeshObjUrl = URL.createObjectURL(
            new Blob([(res as any).data as BlobPart])
          );
          
          resolve(
            Object.assign({
              maskMeshObjUrl,
              meshVolume: (res as any).x_header_obj.volume,
            })
          );
        }
      })
      .catch((error) => {
        reject(error);
      });
  });
}

export async function useBreastObjMesh(name: string) {
  return new Promise<string>((resolve, reject) => {
    http
      .getBlob("/breast_model", { name })
      .then((res) => {
        const breastMeshObjUrl = URL.createObjectURL(
          new Blob([res as BlobPart])
        );
        resolve(breastMeshObjUrl);
      })
      .catch((error) => {
        reject(error);
      });
  });
}

export async function useClearMaskMesh(name: string) {
  let res = http.get<string>("/clearmesh", { name });
  return res;
}
export async function useNrrdRegisterCase(
  requestInfo: IRegRquest
): Promise<ICaseUrls> {
  return new Promise((resolve, reject) => {
    let urls: ICaseRegUrls = { nrrdUrls: [] };
    http
      .getBlob("/casereg", { data: JSON.stringify(requestInfo) })
      .then((zipBlob) => {
        unzipNrrdFiles(zipBlob, urls, resolve, reject);
      });
  });
}
export async function useNrrdOriginCase(name: string): Promise<ICaseUrls> {
  return new Promise((resolve, reject) => {
    let urls: ICaseRegUrls = { nrrdUrls: [] };
    http.getBlob("/caseorigin", { name }).then((zipBlob) => {
      unzipNrrdFiles(zipBlob, urls, resolve, reject);
    });
  });
}
function unzipNrrdFiles(
  zipBlob: any,
  urls: ICaseRegUrls,
  resolve: (value: ICaseUrls | PromiseLike<ICaseUrls>) => void,
  reject: (reason?: any) => void
) {
  const zip = new JSZip();
  // Extract the contents of the zip archive
  zip.loadAsync(zipBlob as any).then((contents) => {
    const nrrdNames = [];
    for (let prop in contents.files) {
      if (prop.includes(".nrrd")) {
        nrrdNames.push(prop);
      }
    }
    const promises: any = [];
    nrrdNames.forEach((name) => {
      const file = contents.files[name];
      promises.push(file.async("arraybuffer"));
    });
    Promise.all(promises)
      .then((values) => {
        values.forEach((item, index) => {
          urls.nrrdUrls.push(URL.createObjectURL(new Blob([item])));
        });
        resolve(urls);
      })
      .catch((err) => {
        reject(err);
      });
  });
}
