import axios, { AxiosRequestConfig } from "axios";
import { getAccessToken, getKeycloak } from "./keycloak";

export interface IHttp {
  get<T>(url: string, params?: unknown): Promise<T>;
  post<T>(url: string, body?: unknown): Promise<T>;
  getBlob<T>(url: string, params?: unknown): Promise<T>;
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

// ============== case converter (snake_case ↔ camelCase) ==============
// Two-way bridge so frontend uses camelCase consistently while the backend
// keeps snake_case. Response: snake → camel. Request body & params: camel → snake.
//
// Aliases handle frontend names that semantically diverge from backend names
// (not just case). Currently: `toolMetadata` (FE) <-> `plugin_metadata` (BE).
const FE_TO_BE_ALIASES: Record<string, string> = {
  toolMetadata: 'plugin_metadata',
};
const BE_TO_FE_ALIASES: Record<string, string> = Object.fromEntries(
  Object.entries(FE_TO_BE_ALIASES).map(([fe, be]) => [be, fe])
);

function toCamel(str: string): string {
  if (BE_TO_FE_ALIASES[str]) return BE_TO_FE_ALIASES[str];
  return str.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function toSnake(str: string): string {
  if (FE_TO_BE_ALIASES[str]) return FE_TO_BE_ALIASES[str];
  return str.replace(/[A-Z]/g, (c) => '_' + c.toLowerCase());
}

function deepConvertKeys(obj: unknown, fn: (s: string) => string): unknown {
  if (Array.isArray(obj)) return obj.map((v) => deepConvertKeys(v, fn));
  if (obj !== null && typeof obj === 'object' && (obj as object).constructor === Object) {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        fn(k),
        deepConvertKeys(v, fn),
      ])
    );
  }
  return obj;
}

const deepCamelize = (obj: unknown) => deepConvertKeys(obj, toCamel);
const deepSnakeize = (obj: unknown) => deepConvertKeys(obj, toSnake);

// ============== request interceptors: automatically add access_token ==============
axios.interceptors.request.use((config: AxiosRequestConfig | any) => {
  // Get token from Keycloak (sole source of truth)
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  } else {
    console.warn('[HTTP Interceptor] ⚠️ No token found from getAccessToken()! Request will be sent WITHOUT Authorization header.');
  }
  // Convert outgoing JSON body & query params from camelCase → snake_case so the
  // backend Pydantic schemas (snake_case) accept them. Skip FormData/Blob/etc.
  if (config.data && !(config.data instanceof FormData) && !(config.data instanceof Blob) && !(config.data instanceof ArrayBuffer)) {
    config.data = deepSnakeize(config.data);
  }
  if (config.params) {
    config.params = deepSnakeize(config.params);
  }
  return config;
});

// ============== response interceptors：handle 401 ==============
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

axios.interceptors.response.use(
  (res) => { res.data = deepCamelize(res.data); return res; },
  async (err) => {
    // not 401 -> reject
    if (err.response?.status !== 401) return Promise.reject(err);

    const originalRequest = err.config;

    // Prevent infinite retry loops
    if (originalRequest._retry) {
      redirectToLogin("Token refresh failed → redirect to login");
      return Promise.reject(err);
    }

    // Try to refresh the token before giving up
    if (!isRefreshing) {
      isRefreshing = true;
      const keycloak = getKeycloak();

      try {
        if (keycloak) {
          await keycloak.updateToken(5);
          const newToken = keycloak.token;
          if (newToken) {
            isRefreshing = false;
            onTokenRefreshed(newToken);

            // Retry original request with new token
            originalRequest._retry = true;
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return axios(originalRequest);
          }
        }
        // No keycloak or no token after refresh
        isRefreshing = false;
        redirectToLogin("Token expired or invalid → redirect to login");
        return Promise.reject(err);
      } catch (refreshErr) {
        isRefreshing = false;
        refreshSubscribers = [];
        redirectToLogin("Token refresh failed → redirect to login");
        return Promise.reject(err);
      }
    }

    // Another request is already refreshing — queue this one
    return new Promise((resolve) => {
      addRefreshSubscriber((newToken: string) => {
        originalRequest._retry = true;
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        resolve(axios(originalRequest));
      });
    });
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
        const xVolumeHeader = res.headers["x-volume"];
        if (xVolumeHeader)
          return { data: res.data, xHeaderObj: JSON.parse(xVolumeHeader) };
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
  delete(url, params) {
    return axios.delete(url, { params }).then((res) => res.data);
  },
};

export default http;
