import axios from "axios";
import { createApiError } from "./lib/apiErrors";

const getApiBaseUrl = () => {
  if (typeof import.meta !== "undefined" && import.meta.env) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof process !== "undefined" && process.env) {
    return process.env.NEXT_PUBLIC_API_URL || process.env.VITE_API_BASE_URL;
  }
  return "http://127.0.0.1:8000/api/";
};

export const generateUUID = () => {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.getRandomValues === "function"
  ) {
    return ("" + 1e7 + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) =>
      (
        Number(c) ^
        (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (Number(c) / 4)))
      ).toString(16),
    );
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const api = axios.create({
  baseURL: getApiBaseUrl() || "http://127.0.0.1:8000/api/",
});

api.interceptors.request.use((config) => {
  const correlationId =
    config.headers["X-Correlation-ID"] ||
    config.headers["X-Request-ID"] ||
    generateUUID();
  config.headers["X-Correlation-ID"] = correlationId;
  config.headers["X-Request-ID"] = correlationId;
  // attach for error logging later
  config.requestId = correlationId;
  config.correlationId = correlationId;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const correlationId =
      error.response?.headers?.["x-correlation-id"] ||
      error.response?.headers?.["x-request-id"] ||
      error.config?.correlationId ||
      error.config?.requestId ||
      "unknown";
    const status = error.response?.status;
    const friendlyMessage = status
      ? createApiError({
          status,
          endpoint: error.config?.url,
          correlationId,
          requestId: correlationId,
          body: error.response?.data,
        }).message
      : "We couldn't complete your request. Please try again in a moment.";
    console.error(
      `[API Error] CorrelationID=${correlationId}`,
      error.response?.data || error.message,
    );
    if (status && status >= 400) {
      error.message = friendlyMessage;
      error.userMessage = friendlyMessage;
      error.status = status;
      error.correlationId = correlationId;
      error.supportRef = correlationId.slice(0, 8);
    }
    return Promise.reject(error);
  },
);

export default api;
