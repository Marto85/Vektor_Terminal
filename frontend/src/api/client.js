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

// Rastreador global de peticiones lentas / cold-start de Render para mostrar aviso en toda la app
const _slowSet = new Set();
let _retryCount = 0;
const _wakeupListeners = new Set();
let _lastWakingState = false;

function _emitWakeupState() {
  const next = _slowSet.size > 0 || _retryCount > 0;
  if (next !== _lastWakingState) {
    _lastWakingState = next;
    _wakeupListeners.forEach((cb) => {
      try {
        cb(next);
      } catch {
        // Ignorar errores de suscriptores desmontados
      }
    });
  }
}

export function subscribeServerWakeup(listener) {
  _wakeupListeners.add(listener);
  listener(_lastWakingState);
  return () => {
    _wakeupListeners.delete(listener);
  };
}

function _clearSlowTimer(config) {
  if (!config) return;
  if (config._vektorSlowTimer) {
    clearTimeout(config._vektorSlowTimer);
    config._vektorSlowTimer = null;
  }
  if (config._vektorSlowId && _slowSet.has(config._vektorSlowId)) {
    _slowSet.delete(config._vektorSlowId);
    _emitWakeupState();
  }
}

let _reqSeq = 0;

if (apiClient?.interceptors?.request) {
  apiClient.interceptors.request.use((config) => {
    const token = getStoredToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    const reqId = ++_reqSeq;
    config._vektorSlowId = reqId;
    config._vektorSlowTimer = setTimeout(() => {
      _slowSet.add(reqId);
      _emitWakeupState();
    }, 3000);
    return config;
  });
}

if (apiClient?.interceptors?.response) {
  apiClient.interceptors.response.use(
    (response) => {
      _clearSlowTimer(response?.config);
      return response;
    },
    async (error) => {
      const config = error?.config;
      _clearSlowTimer(config);

      if (error?.response?.status === 401) {
        const url = String(config?.url || "");
        if (!url.includes("/auth/login")) {
          setStoredToken(null);
          window.dispatchEvent(new Event("vektor:unauthorized"));
        }
        return Promise.reject(error);
      }

      const method = String(config?.method || "get").toLowerCase();
      const status = error?.response?.status;
      const isTransient = !status || status >= 502 || error?.code === "ECONNABORTED";
      if (config && method === "get" && isTransient && !config._vektorRetried) {
        config._vektorRetried = true;
        _retryCount += 1;
        _emitWakeupState();
        try {
          await new Promise((resolve) => setTimeout(resolve, 1600));
          return await apiClient(config);
        } finally {
          _retryCount = Math.max(0, _retryCount - 1);
          _emitWakeupState();
        }
      }

      return Promise.reject(error);
    }
  );
}

export default apiClient;