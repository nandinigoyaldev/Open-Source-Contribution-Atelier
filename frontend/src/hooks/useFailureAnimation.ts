import { useRef, useCallback, RefObject } from 'react';

type AnimName = 'animate-shake' | 'animate-flash' | string;

/**
 * useFailureAnimation
 * - returns { ref, trigger }
 * - put ref on the container element you want to animate
 * - call trigger('animate-shake'|'animate-flash') on failures
 * - respects prefers-reduced-motion
 */
export function useFailureAnimation<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  const trigger = useCallback((animClass: AnimName = 'animate-shake') => {
    const el = ref.current;
    if (!el) return;

    if (typeof window !== 'undefined') {
      const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduced) return;
    }

    el.classList.remove(animClass);
    // force reflow to allow the animation to restart
    void (el.offsetWidth);
    el.classList.add(animClass);

    const onEnd = () => {
      el.classList.remove(animClass);
      el.removeEventListener('animationend', onEnd);
    };
    el.addEventListener('animationend', onEnd);
  }, []);

  return { ref: ref as RefObject<T>, trigger };
}