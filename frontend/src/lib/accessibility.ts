/**
 * Accessibility utilities for the Open Source Contribution Atelier frontend.
 *
 * Provides helpers for ARIA management, focus trapping, keyboard navigation,
 * screen reader announcements, and color-contrast-aware theme utilities.
 */

// ---------------------------------------------------------------------------
//  Focus Management
// ---------------------------------------------------------------------------

/**
 * Trap focus within a container element. Returns a cleanup function that
 * restores the previously-focused element.
 *
 * Usage inside a modal / drawer:
 *   const restore = trapFocus(dialogRef.current);
 *   // … on close: restore();
 */
export function trapFocus(container: HTMLElement): () => void {
  const previouslyFocused = document.activeElement as HTMLElement | null;

  const focusableSelector = [
    "a[href]",
    "button:not([disabled]):not([tabindex='-1'])",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    '[tabindex]:not([tabindex="-1"])',
  ].join(", ");

  function getFocusableElements(): HTMLElement[] {
    return Array.from(
      container.querySelectorAll<HTMLElement>(focusableSelector),
    ).filter((el) => el.offsetParent !== null);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key !== "Tab") return;

    const focusable = getFocusableElements();
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey) {
      if (document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  container.addEventListener("keydown", handleKeyDown);

  // Auto-focus the first focusable element
  const focusable = getFocusableElements();
  if (focusable.length > 0) {
    focusable[0].focus();
  } else {
    container.focus();
  }

  return () => {
    container.removeEventListener("keydown", handleKeyDown);
    previouslyFocused?.focus();
  };
}

/**
 * Move focus to the next or previous focusable element within a container.
 */
export function moveFocus(
  container: HTMLElement,
  direction: "next" | "previous",
): void {
  const focusableSelector = [
    "a[href]",
    "button:not([disabled]):not([tabindex='-1'])",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    '[tabindex]:not([tabindex="-1"])',
  ].join(", ");

  const focusable = Array.from(
    container.querySelectorAll<HTMLElement>(focusableSelector),
  ).filter((el) => el.offsetParent !== null);

  if (focusable.length === 0) return;

  const currentIndex = focusable.indexOf(
    document.activeElement as HTMLElement,
  );

  let nextIndex: number;
  if (direction === "next") {
    nextIndex = currentIndex + 1;
    if (nextIndex >= focusable.length) nextIndex = 0;
  } else {
    nextIndex = currentIndex - 1;
    if (nextIndex < 0) nextIndex = focusable.length - 1;
  }

  focusable[nextIndex].focus();
}

// ---------------------------------------------------------------------------
//  Keyboard Navigation
// ---------------------------------------------------------------------------

/**
 * Determines whether a keyboard event or element indicates active user typing
 * in an input, textarea, select, contenteditable, or ARIA textbox.
 * Used to disable keyboard shortcuts and ensure typing is never hijacked.
 */
export function isTypingTarget(
  targetOrEvent: Event | EventTarget | HTMLElement | null,
): boolean {
  if (!targetOrEvent) return false;

  const target = (
    "target" in (targetOrEvent as Event)
      ? (targetOrEvent as Event).target
      : targetOrEvent
  ) as HTMLElement | null;

  const activeElement =
    typeof document !== "undefined"
      ? (document.activeElement as HTMLElement | null)
      : null;

  const check = (el: HTMLElement | null): boolean => {
    if (!el || typeof el.tagName !== "string") return false;
    const tag = el.tagName.toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return true;
    }
    if (
      el.isContentEditable ||
      el.getAttribute("contenteditable") === "true" ||
      el.getAttribute("contenteditable") === ""
    ) {
      return true;
    }
    if (el.getAttribute("role") === "textbox") {
      return true;
    }
    if (
      el.closest?.(
        'input, textarea, select, [contenteditable="true"], [contenteditable=""], [role="textbox"]',
      )
    ) {
      return true;
    }
    return false;
  };

  return check(target) || check(activeElement);
}

export interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  description: string;
  disableWhileTyping?: boolean;
  handler: (event: KeyboardEvent) => void;
}

/**
 * Register keyboard shortcuts on a container. Returns a cleanup function.
 * Automatically disables shortcuts when typing in inputs/textareas by default.
 */
export function useKeyboardShortcuts(
  container: HTMLElement | null,
  shortcuts: KeyboardShortcut[],
): () => void {
  if (!container) return () => {};

  function handleKeyDown(event: KeyboardEvent) {
    for (const shortcut of shortcuts) {
      if (shortcut.disableWhileTyping !== false && isTypingTarget(event)) {
        continue;
      }

      const keyMatch =
        event.key.toLowerCase() === shortcut.key.toLowerCase();
      const ctrlMatch = shortcut.ctrl
        ? event.ctrlKey || event.metaKey
        : true;
      const shiftMatch = shortcut.shift ? event.shiftKey : true;
      const altMatch = shortcut.alt ? event.altKey : true;

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
        event.preventDefault();
        shortcut.handler(event);
        return;
      }
    }
  }

  container.addEventListener("keydown", handleKeyDown);
  return () => container.removeEventListener("keydown", handleKeyDown);
}

// ---------------------------------------------------------------------------
//  Screen Reader Live Announcements
// ---------------------------------------------------------------------------

/**
 * Create a visually-hidden live region for screen reader announcements.
 * Returns the container element and an announce function.
 */
export function createLiveRegion(
  politeness: "polite" | "assertive" = "polite",
): { element: HTMLDivElement; announce: (message: string) => void } {
  const element = document.createElement("div");
  element.setAttribute("role", "status");
  element.setAttribute("aria-live", politeness);
  element.setAttribute("aria-atomic", "true");
  element.className = "sr-only"; // visually hidden
  document.body.appendChild(element);

  function announce(message: string) {
    // Clear first to force re-announcement of repeated messages
    element.textContent = "";
    requestAnimationFrame(() => {
      element.textContent = message;
    });
  }

  return { element, announce };
}

/**
 * Remove a previously-created live region from the DOM.
 */
export function removeLiveRegion(element: HTMLDivElement): void {
  element.remove();
}

// ---------------------------------------------------------------------------
//  ARIA Helpers
// ---------------------------------------------------------------------------

/**
 * Generate accessible label text for a reel action button.
 */
export function getReelActionLabel(
  action: "like" | "unlike" | "comment" | "share" | "follow" | "unfollow",
  reelTitle?: string,
): string {
  const labels: Record<string, string> = {
    like: "Like this reel",
    unlike: "Unlike this reel",
    comment: "View comments",
    share: "Share reel",
    follow: "Follow creator",
    unfollow: "Unfollow creator",
  };

  return labels[action] ?? action;
}

/**
 * Generate a screen-reader-only description for a reel.
 */
export function getReelDescription(reel: {
  title: string;
  creator: { username: string; role: string };
  likes: number;
  commentsCount: number;
  tags: string[];
}): string {
  const tagList = reel.tags.join(", ");
  return [
    `Reel: ${reel.title}`,
    `By @${reel.creator.username}, ${reel.creator.role}`,
    `${reel.likes.toLocaleString()} likes, ${reel.commentsCount} comments`,
    `Tags: ${tagList}`,
  ].join(". ");
}

/**
 * Validate that an element has the required ARIA attributes.
 * Returns an array of issues (empty = all good).
 */
export function validateAriaAttributes(
  element: HTMLElement,
  requiredAttributes: string[],
): string[] {
  const issues: string[] = [];
  for (const attr of requiredAttributes) {
    if (!element.hasAttribute(attr)) {
      const tagName = element.tagName.toLowerCase();
      const role = element.getAttribute("role") || tagName;
      issues.push(
        `<${role}> is missing required ARIA attribute: ${attr}`,
      );
    }
  }
  return issues;
}

/**
 * Check if an element is focusable.
 */
export function isFocusable(element: HTMLElement): boolean {
  if (element.tabIndex < 0) return false;
  if (element.hasAttribute("disabled")) return false;
  if (element.getAttribute("aria-hidden") === "true") return false;

  const tagName = element.tagName.toLowerCase();
  const focusableTags = [
    "a", "button", "input", "select", "textarea",
  ];

  if (focusableTags.includes(tagName)) return true;
  if (element.hasAttribute("tabindex")) return true;

  return false;
}

// ---------------------------------------------------------------------------
//  Color Contrast Helpers
// ---------------------------------------------------------------------------

/**
 * Calculate relative luminance of a hex color.
 */
export function relativeLuminance(hex: string): number {
  const rgb = hexToRgb(hex);
  if (!rgb) return 0;

  const [r, g, b] = [rgb.r / 255, rgb.g / 255, rgb.b / 255].map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );

  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculate contrast ratio between two hex colors (WCAG 2.0).
 */
export function contrastRatio(color1: string, color2: string): number {
  const l1 = relativeLuminance(color1);
  const l2 = relativeLuminance(color2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Check if a color combination meets WCAG AA or AAA standards.
 */
export function meetsContrastStandard(
  foreground: string,
  background: string,
  level: "AA" | "AAA" = "AA",
  isLargeText = false,
): boolean {
  const ratio = contrastRatio(foreground, background);
  if (level === "AAA") {
    return isLargeText ? ratio >= 4.5 : ratio >= 7;
  }
  // AA
  return isLargeText ? ratio >= 3 : ratio >= 4.5;
}

// ---------------------------------------------------------------------------
//  Internal Helpers
// ---------------------------------------------------------------------------

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const cleaned = hex.replace("#", "");
  const full =
    cleaned.length === 3
      ? cleaned
          .split("")
          .map((c) => c + c)
          .join("")
      : cleaned;

  const result = /^([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(full);
  if (!result) return null;

  return {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16),
  };
}
