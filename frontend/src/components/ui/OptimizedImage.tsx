import React, { useState } from "react";

interface OptimizedImageProps {
  src: string;
  alt: string;
  webpSrc?: string;
  width?: number;
  height?: number;
  loading?: "lazy" | "eager";
  decoding?: "async" | "sync" | "auto";
  className?: string;
  fallbackSrc?: string;
}

const FALLBACK_AVATAR =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Crect fill='%23dcd3c4' width='40' height='40'/%3E%3Ctext fill='%236b5e4e' font-family='monospace' font-size='20' font-weight='bold' x='50%25' y='55%25' text-anchor='middle' dominant-baseline='middle'%3E?%3C/text%3E%3C/svg%3E";

export function OptimizedImage({
  src,
  alt,
  webpSrc,
  width,
  height,
  loading = "lazy",
  decoding = "async",
  className = "",
  fallbackSrc = FALLBACK_AVATAR,
}: OptimizedImageProps) {
  const [imgError, setImgError] = useState(false);

  const imgProps = {
    src: imgError ? fallbackSrc : src,
    alt,
    loading,
    decoding,
    width,
    height,
    className,
    onError: () => setImgError(true),
  };

  if (webpSrc && !imgError) {
    return (
      <picture>
        <source srcSet={webpSrc} type="image/webp" />
        <img {...imgProps} />
      </picture>
    );
  }

  return <img {...imgProps} />;
}
