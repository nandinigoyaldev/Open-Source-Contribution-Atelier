import { Printer, X } from "lucide-react";
import { SocialShareButtons } from "../ui/SocialShareButtons";
import type { CertificateResponse } from "./types";

interface CertificateModalProps {
  isOpen: boolean;
  onClose: () => void;
  username?: string;
  certificateData?: CertificateResponse;
}

export function CertificateModal({
  isOpen,
  onClose,
  username,
  certificateData,
}: CertificateModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-[#FFF9F0] rounded-[2rem] border-8 border-black p-8 sm:p-12 relative flex flex-col justify-between items-center text-center shadow-card bg-dot-grid print:border-none print:shadow-none print:p-0">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 bg-white border-2 border-black p-2 rounded-full hover:bg-surface-low transition-colors print:hidden"
          aria-label="Close certificate"
        >
          <X size={16} />
        </button>

        <div className="space-y-6 w-full border-4 border-dashed border-black/35 rounded-2xl p-6 sm:p-10 relative">
          <div className="text-6xl mb-2">🎓</div>
          <h2 className="text-4xl sm:text-5xl font-black uppercase tracking-tight text-text">
            Certificate of Completion
          </h2>
          <p className="font-mono text-xs text-primary uppercase tracking-widest font-black">
            The Open Source Contribution Atelier
          </p>

          <div className="py-4">
            <p className="text-sm italic text-muted">
              This is officially awarded to
            </p>
            <h3 className="text-3xl sm:text-4xl font-black text-text underline decoration-accent decoration-wavy mt-2">
              {username}
            </h3>
          </div>

          <p className="max-w-xl mx-auto text-sm font-bold leading-relaxed text-text">
            for successfully resolving issues, demonstrating version control
            proficiency, respecting open source etiquette, and completing the
            full 8-module collaborative contribution track.
          </p>

          <div className="grid grid-cols-2 gap-4 max-w-md mx-auto pt-6 text-left border-t border-black/10">
            <div>
              <span className="block text-[10px] text-muted uppercase font-bold">
                Verification Hash
              </span>
              <span
                className="font-mono text-xs font-black truncate block"
                title={
                  certificateData?.certificate?.verification_hash ||
                  "GENERATING..."
                }
              >
                {certificateData?.certificate?.verification_hash ||
                  "GENERATING..."}
              </span>
            </div>
            <div>
              <span className="block text-[10px] text-muted uppercase font-bold">
                Issue Date
              </span>
              <span className="font-mono text-xs font-black block">
                {certificateData?.certificate?.issued_at
                  ? new Date(
                      certificateData.certificate.issued_at,
                    ).toLocaleDateString()
                  : new Date().toLocaleDateString()}
              </span>
            </div>
          </div>

          {certificateData?.certificate?.verification_hash && (
            <div className="mt-4 text-[10px] text-muted font-bold text-center print:block">
              Verify authenticity at:{" "}
              <span className="text-primary underline select-all">
                {window.location.origin}/verify/
                {certificateData.certificate.verification_hash}
              </span>
            </div>
          )}
        </div>

        <div className="mt-8 flex gap-3 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 rounded-lg bg-primary text-black border-4 border-black px-6 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
          >
            <Printer size={16} /> Print Certificate
          </button>
          {certificateData?.certificate?.verification_hash && (
            <SocialShareButtons
              url={`${window.location.origin}/verify/${certificateData.certificate.verification_hash}`}
              title="I just earned my Open Source Contribution Certificate from the Open Source Contribution Atelier!"
            />
          )}
          <button
            onClick={onClose}
            className="rounded-lg bg-white border-4 border-black px-6 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
