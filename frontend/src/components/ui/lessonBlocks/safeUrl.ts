// Link and image URLs reach the page from lesson source, so the schemes that can run script are
// dropped. The two lists differ on purpose and match what the renderer always did: a link refuses
// any `data:` URL, an image only refuses `data:text/html`.

/** Returns the href, or "#" when its scheme could run script. */
export function safeLinkHref(href: string): string {
  const lower = href.toLowerCase().trim();
  if (
    lower.startsWith("javascript:") ||
    lower.startsWith("vbscript:") ||
    lower.startsWith("data:")
  ) {
    return "#";
  }
  return href;
}

/** Returns the src, or "" when its scheme could run script. */
export function safeImageSrc(src: string): string {
  const lower = src.toLowerCase().trim();
  if (
    lower.startsWith("javascript:") ||
    lower.startsWith("vbscript:") ||
    lower.startsWith("data:text/html")
  ) {
    return "";
  }
  return src;
}
