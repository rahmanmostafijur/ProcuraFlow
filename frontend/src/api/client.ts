import axios, { type InternalAxiosRequestConfig } from "axios";

// Production builds talk to the same origin (the host proxies /api to the backend), so the
// httpOnly-cookie and CORS story stays simple. Local dev falls back to the standalone API port.
const DEFAULT_API_BASE_URL = import.meta.env.PROD ? "/api/v1" : "http://localhost:8000/api/v1";
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL;

// The refresh token lives in an httpOnly cookie that scripts cannot read. This flag is only a hint
// that a session probably exists, so anonymous visitors skip a pointless refresh round trip.
const SESSION_HINT_KEY = "procuraflow_has_session";
const LOGIN_PATH = "/login";
const AUTH_ENDPOINTS = ["/auth/login", "/auth/refresh", "/auth/logout"];

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function hasSessionHint(): boolean {
  return localStorage.getItem(SESSION_HINT_KEY) === "1";
}

export function setSessionHint(isSignedIn: boolean): void {
  if (isSignedIn) {
    localStorage.setItem(SESSION_HINT_KEY, "1");
  } else {
    localStorage.removeItem(SESSION_HINT_KEY);
  }
}

export const apiClient = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, undefined, { withCredentials: true });
  setAccessToken(data.access_token);
  return data.access_token as string;
}

function isAuthEndpoint(url: string | undefined): boolean {
  return AUTH_ENDPOINTS.some((endpoint) => url?.startsWith(endpoint));
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as RetryableConfig | undefined;
    // Auth endpoints answer 401 for their own reasons (wrong password, no session); refreshing
    // and bouncing to the login page there would hide the real error.
    const canRetry =
      error.response?.status === 401 && originalRequest && !originalRequest._retry && !isAuthEndpoint(originalRequest.url);
    if (canRetry) {
      originalRequest._retry = true;
      try {
        refreshPromise ??= refreshAccessToken();
        const token = await refreshPromise;
        refreshPromise = null;
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        refreshPromise = null;
        setSessionHint(false);
        setAccessToken(null);
        if (window.location.pathname !== LOGIN_PATH) {
          window.location.href = LOGIN_PATH;
        }
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return "Something went wrong. Please try again.";
}
