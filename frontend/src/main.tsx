import React from "react";
import ReactDOM from "react-dom/client";
import { GoogleOAuthProvider } from "@react-oauth/google";
import App from "./app/App";
import { AuthProvider } from "./features/auth/AuthContext";
import { ThemeProvider } from "./hooks/useTheme";
import { ToastProvider } from "./features/ui/ToastContext";
import { syncOfflineQueue } from "./lib/offlineQueue";
import i18n from "./lib/i18n";
import { I18nextProvider } from "react-i18next";
import "./styles.css";

const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  "27042928964-pbolsldqvdv2hfipblmrcf332evg83v8.apps.googleusercontent.com";

// Register Service Worker
if (typeof window !== "undefined" && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register(import.meta.env.DEV ? "/dev-sw.js?dev-sw" : "/sw.js", {
        type: import.meta.env.DEV ? "module" : "classic",
      })
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
    <I18nextProvider i18n={i18n}>
      <ThemeProvider>
        <AuthProvider>
          <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
            <ToastProvider>
              <App />
            </ToastProvider>
          </GoogleOAuthProvider>
        </AuthProvider>
      </ThemeProvider>
    </I18nextProvider>
  </React.StrictMode>,
);
