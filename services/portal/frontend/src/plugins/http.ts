import axios, { type AxiosRequestConfig } from "axios";
import { IRequests } from "@/models/apiTypes";

const Base_URL = `http://127.0.0.1:8000/api`;
const maxRetries = 3;
const retryDelay = 1000;
axios.defaults.baseURL = Base_URL;

axios.interceptors.request.use((config: AxiosRequestConfig | any) => config);
axios.interceptors.response.use(
  (res) => {
    return res;
  },
  (err) => {
    return Promise.reject(err);
  }
);

// Type

interface IHttp {
  get<T>(url: string, params?: unknown): Promise<T>;
  post<T>(url: string, body?: unknown): Promise<T>;
  getBlob<T>(url: string, params?: unknown): Promise<T>;
  all<T>(requests: Array<IRequests>): Promise<T>;
}

const http: IHttp = {
  get(url, params) {
    return new Promise((resolve, reject) => {
      axios
        .get(url, { params })
        .then((res) => {
          resolve(res.data);
        })
        .catch((err) => {
          reject(err);
        });
    });
  },
  getBlob(url, params) {
    return new Promise((resolve, reject) => {
      axios
        .get(url, { params, responseType: "blob" })
        .then((res) => {
          const x_header_str = res.headers["x-volume"];
          if (!!x_header_str) {
            const x_header_obj = JSON.parse(x_header_str);
            resolve(Object.assign({ data: res.data, x_header_obj }));
          } else {
            resolve(res.data);
          }
        })
        .catch((err) => {
          if(err.response.status === 404){
            resolve(err.response.status)
          }
          reject(err);
        });
    });
  },
  post(url, body) {
    return new Promise((resolve, reject) => {
      axios
        .post(url, body)
        .then((res) => {
          resolve(res.data);
        })
        .catch((err) => {
          reject(err);
        });
    });
  },
  all(requests) {
    return new Promise((resolve, reject) => {
      const requestWithRetry = async (request: IRequests) => {
        let retries = 0;

        while (retries < maxRetries) {
          try {
            const response = await axios.get(request.url, {
              params: request.params,
              responseType: "blob",
            });
            // return response.data;
            const x_header_str = response.headers["x-file-name"];

            if (!!x_header_str) {
              const filename = x_header_str;
              return Object.assign({ data: response.data, filename });
            } else {
              return response.data;
            }
          } catch (error) {
            retries++;
            console.log(`Retrying ${request.url} (attempt ${retries})...`);
            await new Promise((resolve) => setTimeout(resolve, retryDelay));
          }
        }

        throw new Error(`All retry attempts for ${request.url} failed`);
      };

      const retryableRequests = requests.map((request) =>
        requestWithRetry(request)
      );
      Promise.all(retryableRequests)
        .then((results) => {
          resolve(results as any);
        })
        .catch((error) => {
          reject(error);
        });
    });
  },
};

export default http;
