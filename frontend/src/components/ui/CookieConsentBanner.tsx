import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Cookie, X } from "lucide-react";

export function CookieConsentBanner() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check local storage after component mounts
    const consent = localStorage.getItem("cookie-consent");
    if (!consent) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsVisible(true);
    }
  }, []);

  const handleConsent = (status: "granted" | "denied") => {
    localStorage.setItem("cookie-consent", status);
    setIsVisible(false);

    // Dispatch a custom event so other scripts (like analytics) can react immediately
    window.dispatchEvent(
      new CustomEvent("cookieConsentUpdated", { detail: { status } }),
    );
  };

  if (!isVisible) return null;

  return (
    <div
      data-testid="cookie-banner"
      className="fixed bottom-0 left-0 right-0 z-50 p-4 sm:p-6 flex justify-center pointer-events-none"
    >
      <div className="bg-white border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] rounded-xl w-full max-w-4xl p-6 sm:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pointer-events-auto transform transition-all translate-y-0">
        <button
          onClick={() => handleConsent("denied")}
          className="absolute top-4 right-4 text-gray-500 hover:text-black transition-colors"
          aria-label="Close banner"
        >
          <X size={24} strokeWidth={3} />
        </button>

        <div className="flex items-start gap-4 flex-1">
          <div className="hidden sm:flex bg-blue-100 p-3 rounded-full border-2 border-black shrink-0">
            <Cookie size={32} className="text-blue-600" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-black uppercase tracking-tight mb-2">
              We Value Your Privacy
            </h2>
            <p className="text-gray-700 font-medium">
              We use cookies to enhance your browsing experience, serve
              personalized content, and analyze our traffic. By clicking "Accept
              All", you consent to our use of cookies.
              <Link
                to="/privacy"
                className="ml-2 text-blue-600 font-bold hover:underline"
              >
                Read our Privacy Policy.
              </Link>
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto shrink-0 mt-4 md:mt-0">
          <button
            onClick={() => handleConsent("denied")}
            className="px-6 py-3 border-4 border-black bg-white text-black font-bold uppercase rounded-xl hover:bg-gray-100 transition-colors shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none whitespace-nowrap"
          >
            Decline Optional
          </button>
          <button
            onClick={() => handleConsent("granted")}
            className="px-6 py-3 border-4 border-black bg-[#40c463] text-black font-bold uppercase rounded-xl hover:bg-[#32a852] transition-colors shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none whitespace-nowrap"
          >
            Accept All
          </button>
        </div>
      </div>
    </div>
  );
}
