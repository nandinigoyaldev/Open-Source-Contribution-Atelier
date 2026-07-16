/**
 * Social sharing and copy link buttons for certificates.
 *
 * @file CertificateShareButtons.tsx
 * @location frontend/src/components/Certificate/CertificateShareButtons.tsx
 */

import React, { useState } from "react";
import { toast } from "react-hot-toast";

interface CertificateShareButtonsProps {
  certificateUrl: string;
  certificateName: string;
  userName: string;
  className?: string;
}

export const CertificateShareButtons: React.FC<
  CertificateShareButtonsProps
> = ({ certificateUrl, certificateName, userName, className = "" }) => {
  const [copied, setCopied] = useState(false);

  // Share text
  const shareText = `🎉 I just earned my "${certificateName}" certificate on Open Source Contribution Atelier! Check it out:`;

  // Handle copy link
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(certificateUrl);
      setCopied(true);
      toast.success("Link copied to clipboard! 📋", {
        duration: 2000,
        position: "bottom-center",
      });
      setTimeout(() => setCopied(false), 3000);
    } catch (error) {
      toast.error("Failed to copy link. Please try again.");
    }
  };

  // Share on Twitter/X
  const handleTwitterShare = () => {
    const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(certificateUrl)}`;
    window.open(url, "_blank", "width=600,height=400");
  };

  // Share on LinkedIn
  const handleLinkedInShare = () => {
    const url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(certificateUrl)}`;
    window.open(url, "_blank", "width=600,height=400");
  };

  // Share via Web Share API (Mobile)
  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Certificate - ${certificateName}`,
          text: shareText,
          url: certificateUrl,
        });
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          console.error("Share failed:", error);
        }
      }
    } else {
      // Fallback to copy link
      handleCopyLink();
    }
  };

  return (
    <div className={`certificate-share-buttons ${className}`}>
      <div className="flex items-center gap-2 flex-wrap">
        {/* Copy Link Button */}
        <button
          onClick={handleCopyLink}
          className={`
            flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all
            border-2 border-gray-600 hover:border-gray-400
            text-gray-300 hover:text-white
            bg-dark-700 hover:bg-dark-600
            focus:outline-none focus:ring-2 focus:ring-blue-500
          `}
          aria-label="Copy certificate link"
        >
          {copied ? (
            <>
              <span className="text-green-400">✓</span>
              <span>Copied!</span>
            </>
          ) : (
            <>
              <span>📋</span>
              <span>Copy Link</span>
            </>
          )}
        </button>

        {/* Twitter/X Share Button */}
        <button
          onClick={handleTwitterShare}
          className="
            flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all
            border-2 border-[#1DA1F2] hover:border-[#1a8cd8]
            text-[#1DA1F2] hover:text-white
            bg-dark-700 hover:bg-[#1DA1F2]
            focus:outline-none focus:ring-2 focus:ring-[#1DA1F2]
          "
          aria-label="Share on Twitter"
        >
          <svg
            className="w-4 h-4 fill-current"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
          </svg>
          <span>Share</span>
        </button>

        {/* LinkedIn Share Button */}
        <button
          onClick={handleLinkedInShare}
          className="
            flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all
            border-2 border-[#0A66C2] hover:border-[#0958a8]
            text-[#0A66C2] hover:text-white
            bg-dark-700 hover:bg-[#0A66C2]
            focus:outline-none focus:ring-2 focus:ring-[#0A66C2]
          "
          aria-label="Share on LinkedIn"
        >
          <svg
            className="w-4 h-4 fill-current"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
          </svg>
          <span>Share</span>
        </button>

        {/* Share Button (Mobile - Web Share API) */}
        {typeof navigator.share === "function" && (
          <button
            onClick={handleShare}
            className="
              flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all
              border-2 border-blue-500 hover:border-blue-400
              text-blue-400 hover:text-white
              bg-dark-700 hover:bg-blue-600
              focus:outline-none focus:ring-2 focus:ring-blue-500
              md:hidden
            "
            aria-label="Share certificate"
          >
            <span>📤</span>
            <span>Share</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default CertificateShareButtons;
