import axios from "axios";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api/v1";

const TOKEN_STORAGE_KEY = "vektor_access_token";

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignorar errores de almacenamiento en entornos restringidos
  }
}

const createdInstance =
  typeof axios.create === "function"
    ? axios.create({
        baseURL: API_BASE_URL,
        timeout: 45000,
      })
    : null;

const apiClient = createdInstance || axios;

if (apiClient?.interceptors?.request) {
  apiClient.interceptors.request.use((config) => {
    const token = getStoredToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
}

if (apiClient?.interceptors?.response) {
  apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error?.response?.status === 401) {
        const url = String(error?.config?.url || "");
        if (!url.includes("/auth/login")) {
          setStoredToken(null);
          window.dispatchEvent(new Event("vektor:unauthorized"));
        }
      }
      return Promise.reject(error);
    }
  );
}

export default apiClient;