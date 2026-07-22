import React from "react";
import ReactDOM from "react-dom/client";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { Provider } from "react-redux";
import App from "./app/App";
import { store } from "./store";
import { AuthProvider } from "./features/auth/AuthContext";
import { ThemeProvider } from "./hooks/useTheme";
import { ToastProvider } from "./features/ui/ToastContext";
import { syncOfflineQueue } from "./lib/offlineQueue";
import { initKeepAlive } from "./lib/hfKeepAlive";
import { QueryProvider } from "./QueryProvider";
import i18n from "./lib/i18n";
import { I18nextProvider } from "react-i18next";
import "./styles.css";
import "./plugins/coreLessonPlugins";
import { NetworkStatusProvider } from "./context/NetworkStatusContext";
import { initializeTracing } from "./tracing";

// Initialize Sentry before rendering if DSN is set and package is available
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
if (SENTRY_DSN) {
  try {
    const Sentry = await import("@sentry/react");
    Sentry.init({
      dsn: SENTRY_DSN,
      integrations: [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration(),
      ],
      tracesSampleRate: parseFloat(
        import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || "1.0",
      ),
      replaysSessionSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
    });
  } catch {
    console.warn("@sentry/react not available, skipping Sentry init");
  }
}

// Initialize OpenTelemetry tracing before rendering
initializeTracing();

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

// Keep HF Spaces container warm (production only)
initKeepAlive();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <I18nextProvider i18n={i18n}>
        <ThemeProvider>
          <QueryProvider>
            <AuthProvider>
              <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                <ToastProvider>
                  <App />
                </ToastProvider>
              </GoogleOAuthProvider>
            </AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </I18nextProvider>
    </Provider>
  </React.StrictMode>,
);
