import React from "react";
import ReactDOM from "react-dom/client";
import { GoogleOAuthProvider } from "@react-oauth/google";
import App from "./app/App";
import { AuthProvider } from "./features/auth/AuthContext";
import { syncOfflineQueue } from "./lib/offlineQueue";
import "./styles.css";

const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  "27042928964-pbolsldqvdv2hfipblmrcf332evg83v8.apps.googleusercontent.com";

// Register Service Worker
if (typeof window !== "undefined" && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        console.log(
          "[ServiceWorker] Registered with scope:",
          registration.scope,
        );
      })
      .catch((error) => {
        console.error("[ServiceWorker] Registration failed:", error);
      });
  });
}

// Perform initial check/sync of offline queue
syncOfflineQueue();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <App />
      </GoogleOAuthProvider>
    </AuthProvider>
  </React.StrictMode>,
);
