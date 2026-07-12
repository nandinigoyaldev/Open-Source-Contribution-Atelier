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

export default api;
