import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AppRouter } from "./router";
import ScrollToTop from "../components/ScrollToTop";
import { queryClient } from "../lib/queryClient";
import { CommandPalette } from "../components/CommandPalette";
import { ErrorBoundary } from "../components/ui/ErrorBoundary";
import { CookieConsentBanner } from "../components/ui/CookieConsentBanner";
import { NetworkStatusProvider } from "../context/NetworkStatusContext";

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <NetworkStatusProvider>
          <BrowserRouter>
            <AppRouter />
            <ScrollToTop />
            <CommandPalette />
            <CookieConsentBanner />
          </BrowserRouter>
        </NetworkStatusProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
