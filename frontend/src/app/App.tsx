import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "react-hot-toast"; // <-- YEH HUMNE ADD KIYA HAI
import { AppRouter } from "./router";
import ScrollToTop from "../components/ScrollToTop";
import { queryClient } from "../lib/queryClient";
import { CommandPalette } from "../components/CommandPalette";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* Global Toast Configuration */}
        <Toaster 
          position="top-right"
          toastOptions={{
            className: 'bg-gray-900 text-white border border-gray-800 shadow-xl font-sans text-sm',
            duration: 4000,
            success: {
              iconTheme: { primary: '#10B981', secondary: '#ffffff' },
            },
            error: {
              iconTheme: { primary: '#EF4444', secondary: '#ffffff' },
            },
          }} 
        />
        <AppRouter />
        <ScrollToTop />
        <CommandPalette />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;