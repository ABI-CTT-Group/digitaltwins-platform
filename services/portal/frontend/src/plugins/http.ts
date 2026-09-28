import axios, { AxiosRequestConfig } from "axios";
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

// refreash token promise
let refreshPromise: Promise<string | null> | null = null;

// customised refreash token
async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(
        "/refresh",
        {},
        {
          withCredentials: true, // with cookie（refresh_token）
        }
      )
      .then((res) => {
        const newToken = res.data.access_token;
        if (newToken) sessionStorage.setItem("access_token", newToken);
        return newToken;
      })
      .catch((err) => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function redirectToLogin(msg?: string) {
  console.warn(msg || "Redirecting to login page...");
  refreshPromise = null;
  sessionStorage.removeItem("access_token");
  window.location.href = "/";
}

// =============== init ===============
(async () => {
  await loadRuntimeConfig();
  const runtimeConfig = getRuntimeConfig();
  const Base_URL = runtimeConfig.PORTAL_BACKEND_HOST_IP;
  const Port = runtimeConfig.BACKEND_PORT;
  const SSL = runtimeConfig.SSL;

  const endpointUrl = `${SSL ? "https://" : "http://"}${Base_URL}:${Port}/api`;

  axios.defaults.baseURL = endpointUrl;

  // ============== request interceptors: automatically add access_token ==============
  axios.interceptors.request.use((config: AxiosRequestConfig | any) => {
    const token = sessionStorage.getItem("access_token");
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    config.withCredentials = true; // let browser bring cookie（include refresh_token）
    return config;
  });

  // ============== respose interceptors：handle 401 ==============
  axios.interceptors.response.use(
    (res) => res,
    async (err) => {
      const originalRequest = err.config;

      // not 401 -> reject
      if (err.response?.status !== 401) return Promise.reject(err);
      
      if (err.response?.status === 401){
        if (err.response?.data?.detail === "Refresh token missing" || err.response?.data?.detail === "Refresh token invalid"){
          redirectToLogin(err.response?.data?.detail)
          return Promise.reject(err)
        }
      }
      
      // avoid infinite loop
      const newToken = await refreshAccessToken();
      if (!newToken) {
        redirectToLogin("Refresh token expired → redirect to login")
        return Promise.reject(err);
      }

      // update header then send the request again
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return axios(originalRequest);
    }
  );

  http = {
    get(url, params) {
      return axios.get(url, { params }).then((res) => res.data);
    },
    getBlob(url, params) {
      return axios
        .get(url, { params, responseType: "blob" })
        .then((res) => {
          const x_header_str = res.headers["x-volume"];
          if (x_header_str)
            return { data: res.data, x_header_obj: JSON.parse(x_header_str) };
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
            if (x_header_str)
              return { data: response.data, filename: x_header_str };
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
