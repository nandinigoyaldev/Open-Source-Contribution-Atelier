import { useEffect, useState } from "react";

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt(): Promise<void>;
}

export function useInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);

      // Track visits or time limit
      // "Install prompt appears on supported browsers after 2 visits or 5 minutes"
      const visitsStr = localStorage.getItem("pwa_visits");
      const visits = visitsStr ? Number(visitsStr) : 0;
      const sessionStarted = sessionStorage.getItem("pwa_session_started");

      let newVisits = visits;
      if (!sessionStarted) {
        newVisits = visits + 1;
        localStorage.setItem("pwa_visits", String(newVisits));
        sessionStorage.setItem("pwa_session_started", "true");
      }

      const firstVisitTimeStr = localStorage.getItem("pwa_first_visit_time");
      let firstVisitTime = firstVisitTimeStr ? Number(firstVisitTimeStr) : 0;
      if (!firstVisitTime) {
        firstVisitTime = Date.now();
        localStorage.setItem("pwa_first_visit_time", String(firstVisitTime));
      }

      const fiveMinutesPassed = Date.now() - firstVisitTime >= 5 * 60 * 1000;

      if (newVisits >= 2 || fiveMinutesPassed) {
        setShowBanner(true);
      } else {
        // Schedule displaying the prompt after the remaining duration of 5 minutes
        const remainingTime = Math.max(
          0,
          5 * 60 * 1000 - (Date.now() - firstVisitTime),
        );
        const timer = setTimeout(() => {
          setShowBanner(true);
        }, remainingTime);
        return () => clearTimeout(timer);
      }
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener(
        "beforeinstallprompt",
        handleBeforeInstallPrompt,
      );
    };
  }, []);

  const install = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setDeferredPrompt(null);
      setShowBanner(false);
    }
  };

  const dismiss = () => {
    setShowBanner(false);
  };

  return { deferredPrompt, showBanner, install, dismiss };
}
