import { RefreshCw, X } from "lucide-react";
import { useVersionCheck } from "../../hooks/useVersionCheck";

export function UpdateAvailableBanner() {
  const { updateAvailable, dismiss, refresh } = useVersionCheck();

  if (!updateAvailable) return null;

  return (
    <div className="bg-blue-500 text-white border-b-4 border-black font-black px-4 py-3 flex items-center justify-between z-50">
      <div className="flex items-center gap-2 text-sm uppercase">
        <RefreshCw size={16} className="animate-spin" />
        <span>A new version is available!</span>
      </div>
      <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
        <button
          onClick={refresh}
          className="px-4 py-1.5 bg-white text-black text-xs uppercase rounded-lg border-2 border-black hover:-translate-y-0.5 transition shadow-[2px_2px_0_#000]"
        >
          Refresh
        </button>
        <button
          onClick={dismiss}
          className="border-2 border-white bg-transparent hover:bg-blue-600 p-1 rounded-lg transition"
          aria-label="Dismiss update banner"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

export default UpdateAvailableBanner;
