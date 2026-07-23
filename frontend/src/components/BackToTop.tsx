import React, { useState, useEffect, useCallback } from 'react';

interface BackToTopProps {
  /** Scroll threshold in pixels before showing button (default: 300) */
  threshold?: number;
  /** Smooth scroll behavior (default: 'smooth') */
  behavior?: 'smooth' | 'auto';
  /** Custom className for styling */
  className?: string;
  /** Show button on all pages or only specific routes */
  showOnRoutes?: string[];
}

const BackToTop: React.FC<BackToTopProps> = ({
  threshold = 300,
  behavior = 'smooth',
  className = '',
  showOnRoutes,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  // ===== SCROLL HANDLER =====
  const handleScroll = useCallback(() => {
    const scrollY = window.scrollY || window.pageYOffset;
    setIsVisible(scrollY > threshold);
  }, [threshold]);

  // ===== SCROLL TO TOP =====
  const scrollToTop = useCallback(() => {
    window.scrollTo({
      top: 0,
      behavior: behavior,
    });
  }, [behavior]);

  // ===== KEYBOARD SUPPORT =====
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        scrollToTop();
      }
    },
    [scrollToTop]
  );

  // ===== SETUP SCROLL LISTENER =====
  useEffect(() => {
    // Check if component should be shown on current route
    if (showOnRoutes) {
      const currentPath = window.location.pathname;
      if (!showOnRoutes.some((route) => currentPath.includes(route))) {
        return;
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true });
    // Initial check
    handleScroll();

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, [handleScroll, showOnRoutes]);

  // ===== SHOW CONDITION =====
  if (!isVisible) {
    return null;
  }

  // ===== RENDER =====
  return (
    <button
      onClick={scrollToTop}
      onKeyDown={handleKeyDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`
        fixed bottom-6 right-6 z-[999]
        flex items-center justify-center
        w-12 h-12 rounded-full
        bg-emerald-600 hover:bg-emerald-700
        text-white shadow-lg
        transition-all duration-300 ease-in-out
        focus:outline-none focus:ring-4 focus:ring-emerald-400/50
        ${isHovered ? 'scale-110 shadow-xl' : 'scale-100'}
        ${className}
      `}
      aria-label="Back to Top"
      title="Back to Top"
    >
      {/* Arrow Icon */}
      <svg
        className={`w-5 h-5 transition-transform duration-300 ${
          isHovered ? '-translate-y-0.5' : ''
        }`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2.5}
          d="M5 10l7-7m0 0l7 7m-7-7v18"
        />
      </svg>

      {/* Progress Ring (Optional) */}
      <svg
        className="absolute inset-0 w-full h-full -rotate-90"
        viewBox="0 0 48 48"
        style={{ opacity: 0.15 }}
      >
        <circle
          cx="24"
          cy="24"
          r="20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeDasharray="125.6"
          strokeDashoffset={125.6 - (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 125.6}
          className="transition-all duration-300"
        />
      </svg>

      {/* Tooltip on hover */}
      {isHovered && (
        <span className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1.5 text-xs font-medium text-white bg-slate-800 dark:bg-slate-700 rounded-lg whitespace-nowrap shadow-lg">
          Back to Top
          <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 dark:bg-slate-700 rotate-45" />
        </span>
      )}
    </button>
  );
};

export default BackToTop;