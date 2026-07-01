import { useEffect, RefObject } from "react";

const FOCUSABLE_ELEMENTS =
  'a[href], button:not([disabled]), textarea:not([disabled]), input[type="text"]:not([disabled]), input[type="radio"]:not([disabled]), input[type="checkbox"]:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useFocusTrap(
  ref: RefObject<HTMLElement | null>,
  isActive: boolean,
) {
  useEffect(() => {
    if (!isActive || !ref.current) return;

    const element = ref.current;
    const previousFocus = document.activeElement as HTMLElement;

    // Focus the first element on mount
    const timer = setTimeout(() => {
      if (!element) return;
      if (element.contains(document.activeElement)) return;

      const focusableEls =
        element.querySelectorAll<HTMLElement>(FOCUSABLE_ELEMENTS);
      const focusableElements = Array.from(focusableEls).filter(
        (el) =>
          el.tabIndex >= 0 && window.getComputedStyle(el).display !== "none",
      );

      if (focusableElements.length > 0) {
        focusableElements[0].focus();
      } else {
        // If no focusable elements, focus the modal container itself so Tab key starts here
        element.setAttribute("tabindex", "-1");
        element.focus();
      }
    }, 10);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      if (!element) return;

      const focusableEls =
        element.querySelectorAll<HTMLElement>(FOCUSABLE_ELEMENTS);
      const focusableElements = Array.from(focusableEls).filter(
        (el) =>
          el.tabIndex >= 0 && window.getComputedStyle(el).display !== "none",
      );

      if (focusableElements.length === 0) {
        e.preventDefault();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        // Shift + Tab
        if (
          document.activeElement === firstElement ||
          document.activeElement === element
        ) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab
        if (
          document.activeElement === lastElement ||
          document.activeElement === element
        ) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("keydown", handleKeyDown);
      // Restore focus when modal closes
      if (previousFocus && typeof previousFocus.focus === "function") {
        previousFocus.focus();
      }
    };
  }, [isActive, ref]);
}
