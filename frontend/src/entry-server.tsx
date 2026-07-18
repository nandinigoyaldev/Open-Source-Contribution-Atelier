import React from "react";
import ReactDOMServer from "react-dom/server";
import { StaticRouter } from "react-router";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { Provider } from "react-redux";
import App from "./app/App";
import { store } from "./store";
import { AuthProvider } from "./features/auth/AuthContext";
import { ThemeProvider } from "./hooks/useTheme";
import { ToastProvider } from "./features/ui/ToastContext";
import i18n from "./lib/i18n";
import { I18nextProvider } from "react-i18next";
import { NetworkStatusProvider } from "./context/NetworkStatusContext";

import { ServerRouter } from "./app/ServerRouter";

const GOOGLE_CLIENT_ID = "27042928964-pbolsldqvdv2hfipblmrcf332evg83v8.apps.googleusercontent.com";

export function render(url: string) {
  return ReactDOMServer.renderToString(
    <React.StrictMode>
      <Provider store={store}>
        <I18nextProvider i18n={i18n}>
          <ThemeProvider>
            <AuthProvider>
              <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                <ToastProvider>
                  <NetworkStatusProvider>
                    <StaticRouter location={url}>
                      <App>
                        <ServerRouter />
                      </App>
                    </StaticRouter>
                  </NetworkStatusProvider>
                </ToastProvider>
              </GoogleOAuthProvider>
            </AuthProvider>
          </ThemeProvider>
        </I18nextProvider>
      </Provider>
    </React.StrictMode>
  );
}
