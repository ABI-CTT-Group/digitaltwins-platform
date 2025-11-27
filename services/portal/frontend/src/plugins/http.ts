// import axios, { type AxiosRequestConfig } from "axios";
// import { IRequests } from "@/models/apiTypes";
// import { getRuntimeConfig, loadRuntimeConfig } from "./runtime";

// // const Base_URL = import.meta.env.VITE_PORTAL_API_URL;
// // const Port = import.meta.env.VITE_PORTAL_PORT;

// async function bootstrap() {
//   const config = await loadRuntimeConfig();
// }

// bootstrap().catch(console.error);
// const runtimeConfig = getRuntimeConfig();
// const Base_URL = runtimeConfig.API_URL;
// const Port = runtimeConfig.PORT;

// const endpointUrl = `${Base_URL}:${Port}/api`;

// const maxRetries = 3;
// const retryDelay = 1000;
// axios.defaults.baseURL = endpointUrl;

// axios.interceptors.request.use((config: AxiosRequestConfig | any) => config);
// axios.interceptors.response.use(
//   (res) => {
//     return res;
//   },
//   (err) => {
//     return Promise.reject(err);
//   }
// );

// // Type

// interface IHttp {
//   get<T>(url: string, params?: unknown): Promise<T>;
//   post<T>(url: string, body?: unknown): Promise<T>;
//   getBlob<T>(url: string, params?: unknown): Promise<T>;
//   all<T>(requests: Array<IRequests>): Promise<T>;
//   delete<T>(url: string, params?: unknown): Promise<T>;
// }

// const http: IHttp = {
//   get(url, params) {
//     return new Promise((resolve, reject) => {
//       axios
//         .get(url, { params })
//         .then((res) => {
//           resolve(res.data);
//         })
//         .catch((err) => {
//           reject(err);
//         });
//     });
//   },
//   getBlob(url, params) {
//     return new Promise((resolve, reject) => {
//       axios
//         .get(url, { params, responseType: "blob" })
//         .then((res) => {
//           const x_header_str = res.headers["x-volume"];
//           if (!!x_header_str) {
//             const x_header_obj = JSON.parse(x_header_str);
//             resolve(Object.assign({ data: res.data, x_header_obj }));
//           } else {
//             resolve(res.data);
//           }
//         })
//         .catch((err) => {
//           if(err.response.status === 404){
//             resolve(err.response.status)
//           }
//           reject(err);
//         });
//     });
//   },
//   post(url, body) {
//     return new Promise((resolve, reject) => {
//       axios
//         .post(url, body)
//         .then((res) => {
//           resolve(res.data);
//         })
//         .catch((err) => {
//           reject(err);
//         });
//     });
//   },
//   all(requests) {
//     return new Promise((resolve, reject) => {
//       const requestWithRetry = async (request: IRequests) => {
//         let retries = 0;

//         while (retries < maxRetries) {
//           try {
//             const response = await axios.get(request.url, {
//               params: request.params,
//               responseType: "blob",
//             });
//             // return response.data;
//             const x_header_str = response.headers["x-file-name"];

//             if (!!x_header_str) {
//               const filename = x_header_str;
//               return Object.assign({ data: response.data, filename });
//             } else {
//               return response.data;
//             }
//           } catch (error) {
//             retries++;
//             console.log(`Retrying ${request.url} (attempt ${retries})...`);
//             await new Promise((resolve) => setTimeout(resolve, retryDelay));
//           }
//         }

//         throw new Error(`All retry attempts for ${request.url} failed`);
//       };

//       const retryableRequests = requests.map((request) =>
//         requestWithRetry(request)
//       );
//       Promise.all(retryableRequests)
//         .then((results) => {
//           resolve(results as any);
//         })
//         .catch((error) => {
//           reject(error);
//         });
//     });
//   },
//   delete(url, params) {
//     return new Promise((resolve, reject) => {
//       axios
//         .delete(url, { params })
//         .then((res) => {
//           resolve(res.data);
//         })
//         .catch((err) => {
//           reject(err);
//         });
//     });
//   },
// };

// export default http;


import axios, { type AxiosRequestConfig } from "axios";
import { IRequests } from "@/models/apiTypes";
import { getRuntimeConfig, loadRuntimeConfig } from "./runtime";

const maxRetries = 3;
const retryDelay = 1000;

export interface IHttp {
  get<T>(url: string, params?: unknown): Promise<T>;
  post<T>(url: string, body?: unknown): Promise<T>;
  getBlob<T>(url: string, params?: unknown): Promise<T>;
  all<T>(requests: Array<IRequests>): Promise<T>;
  delete<T>(url: string, params?: unknown): Promise<T>;
}


let http: IHttp | null = null;
const queue: Array<() => void> = [];


(async () => {
  await loadRuntimeConfig();
  const runtimeConfig = getRuntimeConfig();
  const Base_URL = runtimeConfig.API_URL;
  const Port = runtimeConfig.PORT;

  const endpointUrl = `${Base_URL}:${Port}/api`;
  
  axios.defaults.baseURL = endpointUrl;
  axios.interceptors.request.use((config: AxiosRequestConfig | any) => config);
  axios.interceptors.response.use((res) => res, (err) => Promise.reject(err));

  http = {
    get(url, params) {
      return axios.get(url, { params }).then((res) => res.data);
    },
    getBlob(url, params) {
      return axios
        .get(url, { params, responseType: "blob" })
        .then((res) => {
          const x_header_str = res.headers["x-volume"];
          if (x_header_str) return { data: res.data, x_header_obj: JSON.parse(x_header_str) };
          return res.data;
        })
        .catch((err) => {
          if (err.response?.status === 404) return 404;
          throw err;
        });
    },
    post(url, body) {
      return axios.post(url, body).then((res) => res.data);
    },
    all(requests) {
      const requestWithRetry = async (request: IRequests) => {
        let retries = 0;
        while (retries < maxRetries) {
          try {
            const response = await axios.get(request.url, {
              params: request.params,
              responseType: "blob",
            });
            const x_header_str = response.headers["x-file-name"];
            if (x_header_str) return { data: response.data, filename: x_header_str };
            return response.data;
          } catch (error) {
            retries++;
            await new Promise((r) => setTimeout(r, retryDelay));
          }
        }
        throw new Error(`All retry attempts for ${request.url} failed`);
      };

      return Promise.all(requests.map(requestWithRetry)) as any;
    },
    delete(url, params) {
      return axios.delete(url, { params }).then((res) => res.data);
    },
  };


  queue.forEach((resolve) => resolve());
})();

function waitForHttp(): Promise<IHttp> {
  if (http) return Promise.resolve(http);
  return new Promise((resolve) => queue.push(() => resolve(http!)));
}


const exportedHttp: IHttp = {
  get: (url, params) => waitForHttp().then((h) => h.get(url, params)),
  post: (url, body) => waitForHttp().then((h) => h.post(url, body)),
  getBlob: (url, params) => waitForHttp().then((h) => h.getBlob(url, params)),
  delete: (url, params) => waitForHttp().then((h) => h.delete(url, params)),
  all: (requests) => waitForHttp().then((h) => h.all(requests)),
};

export default exportedHttp;
