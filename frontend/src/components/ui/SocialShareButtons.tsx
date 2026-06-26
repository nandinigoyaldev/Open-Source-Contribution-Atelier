import React from "react";

interface SocialShareButtonsProps {
  url: string;
  title: string;
  hashtags?: string;
}

export function SocialShareButtons({
  url,
  title,
  hashtags = "OpenSource,ContributionAtelier",
}: SocialShareButtonsProps) {
  const encodedUrl = encodeURIComponent(url);
  const encodedTitle = encodeURIComponent(title);
  const encodedHashtags = encodeURIComponent(hashtags);

  // Twitter Web Intent
  const twitterUrl = `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedTitle}&hashtags=${encodedHashtags}`;

  // LinkedIn Sharing
  // Note: LinkedIn pulls OG tags from the URL, so the URL must be publicly accessible.
  const linkedinUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`;

  return (
    <div className="flex gap-3 print:hidden">
      {/* Twitter / X Share Button */}
      <a
        href={twitterUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share to Twitter/X"
        className="flex items-center justify-center w-12 h-12 rounded-lg bg-black text-white border-4 border-black hover:-translate-y-0.5 hover:shadow-card-sm active:translate-y-0.5 active:shadow-none transition-all cursor-pointer"
      >
        <svg
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      </a>

      {/* LinkedIn Share Button */}
      <a
        href={linkedinUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share to LinkedIn"
        className="flex items-center justify-center w-12 h-12 rounded-lg bg-[#0A66C2] text-white border-4 border-black hover:-translate-y-0.5 hover:shadow-card-sm active:translate-y-0.5 active:shadow-none transition-all cursor-pointer"
      >
        <svg
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
        </svg>
      </a>
    </div>
  );
}
