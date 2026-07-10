import { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";

export function ScrollToTop() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const toggleVisibility = () => {
      if (window.scrollY > 300) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    window.addEventListener("scroll", toggleVisibility, { passive: true });

    // Check initially in case the user reloads while scrolled down
    toggleVisibility();

    return () => window.removeEventListener("scroll", toggleVisibility);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  if (!isVisible) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={scrollToTop}
      className="fixed bottom-24 right-6 p-3 rounded-full bg-accent text-black border-4 border-black shadow-card hover:shadow-none hover:translate-x-1 hover:translate-y-1 transition-all z-50 focus:outline-none focus:ring-4 focus:ring-primary dark:bg-[#2e2924] dark:text-[#f0ebe2] dark:border-black"
      aria-label="Scroll to top"
      data-testid="scroll-to-top"
    >
      <ArrowUp className="w-6 h-6 stroke-[3]" />
    </button>
  );
}
