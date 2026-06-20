import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AppRouter } from "./router";
import ScrollToTop from "../components/ScrollToTop";
import { queryClient } from "../lib/queryClient";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRouter />
        <ScrollToTop />
        <CommandPalette />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
