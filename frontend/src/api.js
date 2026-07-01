import axios from "axios";

const api = axios.create({
  // Uses Vercel environment variable in production, falls back to local dev server
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/",
});

export default api;
