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

// ============== camelCase converter (snake_case → camelCase) ==============
// Applied on response data so that frontend code can use camelCase consistently.
// The backend field names are preserved as-is; this layer bridges the gap.
function toCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function deepCamelize(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(deepCamelize);
  if (obj !== null && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        toCamel(k),
        deepCamelize(v),
      ])
    );
  }
  return obj;
}

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
  delete(url, params) {
    return axios.delete(url, { params }).then((res) => res.data);
  },
};

export default http;
