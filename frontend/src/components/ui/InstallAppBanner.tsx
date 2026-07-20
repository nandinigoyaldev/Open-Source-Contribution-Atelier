import React from "react";
import { useInstallPrompt } from "../../hooks/useInstallPrompt";
import { Download, X } from "lucide-react";

export function InstallAppBanner() {
  const { showBanner, install, dismiss } = useInstallPrompt();

  if (!showBanner) return null;

  return (
    <div className="bg-[#ffb5e8] text-black border-b-4 border-black font-black px-4 py-3.5 flex flex-col sm:flex-row items-center justify-between gap-3 z-50">
      <div className="flex items-center gap-2 text-sm uppercase">
        <Download size={16} />
        <span>
          Install Atelier App for full offline access & a faster experience!
        </span>
      </div>
      <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
        <button
          onClick={install}
          className="px-4 py-1.5 bg-black text-white text-xs uppercase rounded-lg border-2 border-black hover:-translate-y-0.5 transition shadow-[2px_2px_0_#000]"
        >
          Install App
        </button>
        <button
          onClick={dismiss}
          className="border-2 border-black bg-white hover:bg-gray-100 p-1 rounded-lg transition"
          aria-label="Dismiss install banner"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

export default InstallAppBanner;
