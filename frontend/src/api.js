import axios from "axios";

const getApiBaseUrl = () => {
  if (typeof import.meta !== "undefined" && import.meta.env) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof process !== "undefined" && process.env) {
    return process.env.NEXT_PUBLIC_API_URL || process.env.VITE_API_BASE_URL;
  }
  return "http://127.0.0.1:8000/api/";
};

const api = axios.create({
  baseURL: getApiBaseUrl() || "http://127.0.0.1:8000/api/",
});

api.interceptors.request.use((config) => {
  const requestId = crypto.randomUUID();
  config.headers["X-Request-ID"] = requestId;
  // attach for error logging later
  config.requestId = requestId;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestId = error.config?.requestId || "unknown";
    console.error(
      `[API Error] ReqID=${requestId}`,
      error.response?.data || error.message,
    );
    return Promise.reject(error);
  },
);

export default api;
