import React, { useState } from "react";
import ReportIssueModal from "./ReportIssueModal";

export default function ReportIssueButton() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 px-4 py-3 bg-black text-white font-bold rounded-full shadow-[4px_4px_0px_0px_#ffb5e8] hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_#ffb5e8] active:translate-y-1 active:shadow-none transition-all flex items-center gap-2"
        aria-label="Report Issue"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
        <span>Report Issue</span>
      </button>

      <ReportIssueModal open={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}
