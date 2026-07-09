import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { useState, useEffect } from "react";

import { AppRouter } from "./router";
import { queryClient } from "../lib/queryClient";
import { ThemeProvider } from '../context/ThemeContext';
import { ThemeToggle } from '../components/ui/ThemeToggle';
import { CommandPalette } from "../components/CommandPalette";
import ReportIssueButton from "../components/ui/ReportIssueButton";
import { NotificationProvider } from "../features/notifications/NotificationContext";
import { ScrollToTop } from "../components/ui/ScrollToTop";

// Pure React Onboarding Tour Step Definition Type Map
interface TourStep {
  target: string;
  title: string;
  content: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    target: '[data-tour="catalog"]',
    title: "📚 Lesson Catalog",
    content: "Explore specialized modules and select programming or technical practice problems curated for your track.",
  },
  {
    target: '[data-tour="dashboard-stats"]',
    title: "📊 Dashboard Standings",
    content: "Keep track of active active contribution logs, response SLAs, and monitor metrics dynamically.",
  },
  {
    target: '[data-tour="achievements"]',
    title: "🏆 Achievements Grid",
    content: "Track gamified unlocks, collect progress badges, and view active learning milestones directly.",
  },
  {
    target: '[data-tour="sandbox"]',
    title: "💻 Interactive Terminal Sandbox",
    content: "Compile and execute code setups live over isolated runtime workers equipped with multi-theme support.",
  },
];

export function App() {
  const [currentStep, setCurrentStep] = useState<number>(-1);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number; height: number } | null>(null);

  useEffect(() => {
    // Automatically trigger onboarding if no historical tour indicator exists
    const hasCompletedTour = localStorage.getItem("has-completed-onboarding-tour");
    if (!hasCompletedTour) {
      setCurrentStep(0);
    }

    // Custom global event listener allowing configuration resets directly out of settings pages
    const handleRestartTour = () => setCurrentStep(0);
    window.addEventListener("restart-onboarding-tour", handleRestartTour);
    return () => window.removeEventListener("restart-onboarding-tour", handleRestartTour);
  }, []);

  useEffect(() => {
    if (currentStep < 0 || currentStep >= TOUR_STEPS.length) {
      setCoords(null);
      return;
    }

    const step = TOUR_STEPS[currentStep];
    const element = document.querySelector(step.target);

    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
      const rect = element.getBoundingClientRect();
      setCoords({
        top: rect.top + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
        height: rect.height,
      });
    } else {
      // If a target element isn't currently loaded into the visible DOM viewport frame, step forward gracefully
      const timer = setTimeout(() => {
        setCoords(null);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [currentStep]);

  const handleNext = () => {
    if (currentStep === TOUR_STEPS.length - 1) {
      handleSkip();
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSkip = () => {
    setCurrentStep(-1);
    localStorage.setItem("has-completed-onboarding-tour", "true");
  };

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <NotificationProvider>
            <div className="min-h-screen bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100 transition-colors duration-300">

              {/* Global Toast Configuration */}
              <Toaster
                position="top-right"
                toastOptions={{
                  className:
                    "bg-gray-900 text-white border border-gray-800 shadow-xl font-sans text-sm",
                  duration: 4000,
                  success: {
                    iconTheme: { primary: "#10B981", secondary: "#ffffff" },
                  },
                  error: {
                    iconTheme: { primary: "#EF4444", secondary: "#ffffff" },
                  },
                }}
              />
              <AppRouter />
              <ScrollToTop />
              <CommandPalette />
              <ReportIssueButton />

              {/* Pure React Onboarding Modals Highlight Tour Overlay Portal */}
              {currentStep >= 0 && coords && (
                <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-50 overflow-hidden">
                  {/* Backdrop highlight layout wrapper */}
                  <div 
                    className="absolute border-[4px] border-amber-400 bg-black/10 dark:bg-white/5 shadow-[0_0_0_9999px_rgba(0,0,0,0.6)] rounded-lg transition-all duration-300 pointer-events-auto"
                    style={{
                      top: `${coords.top - 6}px`,
                      left: `${coords.left - 6}px`,
                      width: `${coords.width + 12}px`,
                      height: `${coords.height + 12}px`,
                    }}
                  />

                  {/* Neobrutalist Floating Step Prompt Guide Tooltip */}
                  <div 
                    className="absolute p-5 bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card w-80 pointer-events-auto transition-all duration-300"
                    style={{
                      top: `${coords.top + coords.height + 16}px`,
                      left: `${Math.max(16, Math.min(window.innerWidth - 340, coords.left))}px`,
                    }}
                  >
                    <h4 className="text-base font-black text-black dark:text-[#f0ebe2] mb-1">
                      {TOUR_STEPS[currentStep].title}
                    </h4>
                    <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed mb-4">
                      {TOUR_STEPS[currentStep].content}
                    </p>
                    <div className="flex items-center justify-between">
                      <button 
                        onClick={handleSkip}
                        className="text-xs font-bold text-gray-400 hover:text-black dark:hover:text-white transition"
                      >
                        Skip Tour
                      </button>
                      <div className="flex gap-1.5">
                        {currentStep > 0 && (
                          <button 
                            onClick={handleBack}
                            className="px-2.5 py-1 text-xs font-bold border-2 border-black rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 bg-white dark:bg-black text-black dark:text-white transition"
                          >
                            Back
                          </button>
                        )}
                        <button 
                          onClick={handleNext}
                          className="px-3 py-1 text-xs font-black bg-[#ffb5e8] border-2 border-black rounded-md text-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all"
                        >
                          {currentStep === TOUR_STEPS.length - 1 ? "Finish" : "Next ❯"}
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 text-[10px] font-black text-right text-gray-400">
                      Step {currentStep + 1} of {TOUR_STEPS.length}
                    </div>
                  </div>
                </div>
              )}

            </div>
          </NotificationProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
