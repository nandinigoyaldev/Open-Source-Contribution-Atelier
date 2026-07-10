import React, { useEffect, useState, useRef } from "react";
import { fetchApi } from "../../lib/api";

interface ReadingProgressTrackerProps {
  lessonSlug: string;
  containerSelector?: string;
}

export function ReadingProgressTracker({
  lessonSlug,
  containerSelector = ".markdown-body",
}: ReadingProgressTrackerProps) {
  const [progress, setProgress] = useState(0);
  const [initialProgressLoaded, setInitialProgressLoaded] = useState(false);
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Elements tracking
  const elementsRef = useRef<Element[]>([]);
  const visibleElements = useRef<Set<number>>(new Set());

  // Fetch initial progress
  useEffect(() => {
    let isMounted = true;

    const fetchProgress = async () => {
      try {
        const response = await fetchApi(
          `/api/progress/reading-position/?lesson=${lessonSlug}`,
        );
        if (isMounted && response?.progress !== undefined) {
          setProgress(response.progress);
          setInitialProgressLoaded(true);

          // If we have a saved progress, try to scroll to it
          if (response.progress > 0) {
            setTimeout(() => {
              const container = document.querySelector(containerSelector);
              if (container) {
                const elements = Array.from(container.children);
                if (elements.length > 0) {
                  const targetIndex = Math.floor(
                    (response.progress / 100) * elements.length,
                  );
                  const targetElement =
                    elements[Math.min(targetIndex, elements.length - 1)];
                  targetElement?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
                }
              }
            }, 1000); // Give markdown time to render
          }
        }
      } catch (err) {
        console.error("Failed to load reading progress:", err);
      }
    };

    fetchProgress();

    return () => {
      isMounted = false;
    };
  }, [lessonSlug, containerSelector]);

  // Sync progress to backend
  const syncProgressToBackend = (currentProgress: number) => {
    if (syncTimeoutRef.current) {
      clearTimeout(syncTimeoutRef.current);
    }

    // Debounce for 2 seconds
    syncTimeoutRef.current = setTimeout(async () => {
      try {
        await fetchApi("/api/progress/reading-position/", {
          method: "POST",
          body: JSON.stringify({
            lesson: lessonSlug,
            progress: currentProgress,
          }),
        });
      } catch (err) {
        console.error("Failed to save reading progress:", err);
      }
    }, 2000);
  };

  // Setup Intersection Observer
  useEffect(() => {
    if (!initialProgressLoaded) return;

    // Slight delay to ensure content is fully rendered
    const timer = setTimeout(() => {
      const container = document.querySelector(containerSelector);
      if (!container) return;

      const elements = Array.from(container.children);
      elementsRef.current = elements;

      if (elements.length === 0) return;

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            const index = elementsRef.current.indexOf(entry.target);
            if (index === -1) return;

            if (entry.isIntersecting) {
              visibleElements.current.add(index);
            } else {
              visibleElements.current.delete(index);
            }
          });

          if (visibleElements.current.size > 0) {
            const maxVisibleIndex = Math.max(
              ...Array.from(visibleElements.current),
            );
            // Calculate progress based on the furthest visible element
            const calculatedProgress = Math.min(
              100,
              Math.round(
                ((maxVisibleIndex + 1) / elementsRef.current.length) * 100,
              ),
            );

            setProgress((prev) => {
              if (calculatedProgress > prev) {
                // Only increase progress, don't decrease if they scroll up
                syncProgressToBackend(calculatedProgress);
                return calculatedProgress;
              }
              return prev;
            });
          }
        },
        {
          root: null, // viewport
          rootMargin: "0px",
          threshold: 0.1, // Trigger when 10% visible
        },
      );

      elements.forEach((el) => observer.observe(el));

      return () => {
        observer.disconnect();
      };
    }, 1500);

    return () => clearTimeout(timer);
  }, [lessonSlug, initialProgressLoaded, containerSelector]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);
    };
  }, []);

  if (progress === 0) return null;

  return (
    <div className="fixed top-0 left-0 w-full z-50 pointer-events-none">
      <div
        className="h-1 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] transition-all duration-300 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
