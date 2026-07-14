import React, { useRef, useState } from "react";
import { Printer, X, Image, FileImage, Loader2 } from "lucide-react";
import { toPng, toSvg } from "html-to-image";
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
  const certificateRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);

  if (!isOpen) return null;

  // Handler to export layout node as a high-quality PNG image file
  const exportAsPng = async () => {
    if (!certificateRef.current) return;
    setIsExporting(true);
    try {
      const dataUrl = await toPng(certificateRef.current, {
        quality: 1.0,
        pixelRatio: 3, // Multiplies resolution scale for crisp high-density asset exports
        backgroundColor: "#FFF9F0",
      });
      const link = document.createElement("a");
      link.download = `Certificate-${username || "User"}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error("Failed to render and download PNG image:", error);
    } finally {
      setIsExporting(false);
    }
  };

  // Handler to export layout node cleanly as an SVG vector file format
  const exportAsSvg = async () => {
    if (!certificateRef.current) return;
    setIsExporting(true);
    try {
      const dataUrl = await toSvg(certificateRef.current, {
        backgroundColor: "#FFF9F0",
      });
      const link = document.createElement("a");
      link.download = `Certificate-${username || "User"}.svg`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error("Failed to render and download SVG file:", error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-[#FFF9F0] rounded-[2rem] border-8 border-black p-8 sm:p-12 relative flex flex-col justify-between items-center text-center shadow-card bg-dot-grid certificate-printable print:border-none print:shadow-none print:p-0 print:bg-white print:text-black">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 bg-white border-2 border-black p-2 rounded-full hover:bg-surface-low transition-colors print:hidden"
          aria-label="Close certificate"
        >
          <X size={16} />
        </button>

        {/* Bound layout wrapper targeting DOM elements for capture structure conversion */}
        <div
          ref={certificateRef}
          className="space-y-6 w-full border-4 border-dashed border-black/35 rounded-2xl p-6 sm:p-10 relative bg-[#FFF9F0]"
        >
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

        {/* Action Controls Section */}
        <div className="mt-8 flex flex-wrap justify-center gap-3 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 rounded-lg bg-primary text-black border-4 border-black px-5 py-2.5 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
          >
            <Printer size={16} /> Print
          </button>

          {/* New Feature Interactive Action Exporters (#1233) */}
          <button
            onClick={exportAsPng}
            disabled={isExporting}
            className="flex items-center gap-2 rounded-lg bg-amber-400 text-black border-4 border-black px-5 py-2.5 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer disabled:opacity-60"
          >
            {isExporting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Image size={16} />
            )}{" "}
            Download PNG
          </button>

          <button
            onClick={exportAsSvg}
            disabled={isExporting}
            className="flex items-center gap-2 rounded-lg bg-teal-400 text-black border-4 border-black px-5 py-2.5 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer disabled:opacity-60"
          >
            {isExporting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <FileImage size={16} />
            )}{" "}
            Download SVG
          </button>

          {certificateData?.certificate?.verification_hash && (
            <SocialShareButtons
              url={`${window.location.origin}/verify/${certificateData.certificate.verification_hash}`}
              title="I just earned my Open Source Contribution Certificate from the Open Source Contribution Atelier!"
            />
          )}

          <button
            onClick={onClose}
            className="rounded-lg bg-white border-4 border-black px-5 py-2.5 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
