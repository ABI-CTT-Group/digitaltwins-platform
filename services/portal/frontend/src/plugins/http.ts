import axios, { AxiosRequestConfig } from "axios";
import { IRequests } from "@/models/apiTypes";
import { getAccessToken } from "./keycloak";

const maxRetries = 3;
const retryDelay = 1000;

export interface IHttp {
  get<T>(url: string, params?: unknown): Promise<T>;
  post<T>(url: string, body?: unknown): Promise<T>;
  getBlob<T>(url: string, params?: unknown): Promise<T>;
  all<T>(requests: Array<IRequests>): Promise<T>;
  delete<T>(url: string, params?: unknown): Promise<T>;
}

function redirectToLogin(msg?: string) {
  console.warn(msg || "Redirecting to login page...");
  sessionStorage.removeItem("access_token"); // Clean up any legacy data
  if (window.location.pathname !== "/") {
    window.location.href = "/";
  }
}

// =============== init ===============
// All API requests go through nginx reverse proxy at /api (same-origin, no CORS)
axios.defaults.baseURL = "/api";

// ============== request interceptors: automatically add access_token ==============
axios.interceptors.request.use((config: AxiosRequestConfig | any) => {
  // Get token from Keycloak (sole source of truth)
  const token = getAccessToken();

  // 🔍 DEBUG: log token status for every outgoing request
  console.log(`[HTTP Interceptor] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
  console.log(`[HTTP Interceptor] Token present: ${!!token}`);
  if (token) {
    console.log(`[HTTP Interceptor] Token (first 50 chars): ${token.substring(0, 50)}...`);
    console.log(`[HTTP Interceptor] Full token:`, token);
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  } else {
    console.warn('[HTTP Interceptor] ⚠️ No token found from getAccessToken()! Request will be sent WITHOUT Authorization header.');
  }
  return config;
});

// ============== response interceptors：handle 401 ==============
axios.interceptors.response.use(
  (res) => res,
  async (err) => {
    // not 401 -> reject
    if (err.response?.status !== 401) return Promise.reject(err);

    // 401 → redirect to login (Keycloak token expired or invalid)
    redirectToLogin("Token expired or invalid → redirect to login");
    return Promise.reject(err);
  }
);

const http: IHttp = {
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

export default http;
