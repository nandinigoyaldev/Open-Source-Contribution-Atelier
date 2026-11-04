import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAppDispatch } from "../store/hooks";

import { AppRouter } from "./router";
import { queryClient } from "../lib/queryClient";
import { CommandPalette } from "../components/CommandPalette";
import { DocSearchModal } from "../components/docs/DocSearchModal";
import { KeyboardShortcutsModal } from "../components/KeyboardShortcutsModal";
import ReportIssueButton from "../components/ui/ReportIssueButton";
import { ErrorBoundary } from "../components/ui/ErrorBoundary";
import { NotificationProvider } from "../features/notifications/NotificationContext";
import { WebSocketStatusIndicator } from "../components/WebSocketStatus/WebSocketStatusIndicator";
import { CustomCursor } from "../components/CustomCursor";
import { OfflineBanner } from "../components/ui/OfflineBanner";
import { InstallAppBanner } from "../components/ui/InstallAppBanner";
import { UpdateAvailableBanner } from "../components/ui/UpdateAvailableBanner";
import { ConflictResolutionModal } from "../components/ui/ConflictResolutionModal";
import { SyncStatusIndicator } from "../components/ui/SyncStatusIndicator";
import { useSlowConnection } from "../hooks/useSlowConnection";

// ✅ Import BackToTop Component
import BackToTop from "../components/BackToTop";
import { SkipLink } from "../components/ui/SkipLink";

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
    content:
      "Explore specialized modules and select programming or technical practice problems curated for your track.",
  },
  {
    target: '[data-tour="dashboard-stats"]',
    title: "📊 Dashboard Standings",
    content:
      "Keep track of active active contribution logs, response SLAs, and monitor metrics dynamically.",
  },
  {
    target: '[data-tour="achievements"]',
    title: "🏆 Achievements Grid",
    content:
      "Track gamified unlocks, collect progress badges, and view active learning milestones directly.",
  },
  {
    target: '[data-tour="sandbox"]',
    title: "💻 Interactive Terminal Sandbox",
    content:
      "Compile and execute code setups live over isolated runtime workers equipped with multi-theme support.",
  },
];

export function App({ children }: { children?: React.ReactNode }) {
  const location = useLocation();
  const dispatch = useAppDispatch();
  const { isConnectionSlow } = useSlowConnection(1500);

  useEffect(() => {
    dispatch({
      type: "LOCATION_CHANGE",
      payload: { pathname: location.pathname },
    });
  }, [location.pathname, dispatch]);

  const [currentStep, setCurrentStep] = useState<number>(-1);
  const [coords, setCoords] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);

  useEffect(() => {
    // Automatically trigger onboarding if no historical tour indicator exists
    const hasCompletedTour = localStorage.getItem(
      "has-completed-onboarding-tour",
    );
    if (!hasCompletedTour) {
      setCurrentStep(0);
    }

    // Custom global event listener allowing configuration resets directly out of settings pages
    const handleRestartTour = () => setCurrentStep(0);
    window.addEventListener("restart-onboarding-tour", handleRestartTour);
    return () =>
      window.removeEventListener("restart-onboarding-tour", handleRestartTour);
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
      <NotificationProvider>
        <div className="min-h-screen bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100 transition-colors duration-300">
          <SkipLink />
          <OfflineBanner />
          <InstallAppBanner />
          <UpdateAvailableBanner />
          <ConflictResolutionModal />
          <div className="fixed top-20 right-3 z-40">
            <SyncStatusIndicator />
          </div>
          {/* Reactive High-Latency Unstable Quality Toast Alert Banner */}
          {isConnectionSlow && (
            <div 
              role="alert" 
              className="fixed bottom-6 left-6 z-50 p-4 max-w-md bg-amber-500/10 border border-amber-500/30 rounded-xl backdrop-blur-md shadow-2xl transition-all duration-300 transform scale-100 ease-out animate-fade-in"
            >
              <div className="flex items-start space-x-3">
                <span className="text-lg" aria-hidden="true">⚠️</span>
                <div>
                  <h4 className="text-sm font-bold text-amber-400">Unstable Network Detected</h4>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                    Your changes will sync automatically when your internet connection stabilizes.
                  </p>
                </div>
              </div>
            </div>
          )}
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
          <ErrorBoundary>
            {children || <AppRouter />}
          </ErrorBoundary>
          <CommandPalette />
          <DocSearchModal />
          <KeyboardShortcutsModal />
          <CustomCursor />
          <WebSocketStatusIndicator url="" />

          {/* Pure React Onboarding Modals Highlight Tour Overlay Portal */}
          {currentStep >= 0 && currentStep < TOUR_STEPS.length && coords && (
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
                    left: `${coords.left + coords.width / 2 - 160}px`,
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
                        {currentStep === TOUR_STEPS.length - 1
                          ? "Finish"
                          : "Next ❯"}
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
    </QueryClientProvider>
  );
}

export default App;
