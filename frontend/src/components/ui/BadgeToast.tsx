import { useCallback, useEffect, useRef, useState } from "react";
import { X, Award } from "lucide-react";

export interface BadgeToastData {
  id: string;
  name: string;
  icon: string;
  desc: string;
}

const AUTO_DISMISS_MS = 6000;

interface BadgeToastProps {
  badge: BadgeToastData;
  onDismiss: (id: string) => void;
}

export function BadgeToast({ badge, onDismiss }: BadgeToastProps) {
  const [visible, setVisible] = useState(false);
  // Use a ref to track dismissal so the dismiss callback stays stable
  const isDismissingRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const dismiss = useCallback(() => {
    if (isDismissingRef.current) return;
    isDismissingRef.current = true;
    setVisible(false);
    timerRef.current = setTimeout(() => onDismiss(badge.id), 350);
  }, [onDismiss, badge.id]);

  // Auto-dismiss after AUTO_DISMISS_MS
  useEffect(() => {
    const auto = setTimeout(dismiss, AUTO_DISMISS_MS);
    return () => {
      clearTimeout(auto);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [dismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      onClick={dismiss}
      className={`
        relative w-full max-w-xs cursor-pointer select-none
        rounded-2xl border-4 border-black bg-white
        shadow-[5px_5px_0px_#000] dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-[5px_5px_0px_#2e2924]
        p-4 flex items-start gap-3
        transition-all duration-300 ease-out
        ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}
      `}
    >
      {/* Accent stripe */}
      <div className="absolute top-0 left-0 h-full w-1.5 rounded-l-xl bg-accent" />

      {/* Badge icon */}
      <div
        className="ml-1 flex-shrink-0 text-4xl leading-none"
        aria-hidden="true"
      >
        {badge.icon}
      </div>

      {/* Text content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <Award size={11} className="text-primary flex-shrink-0" />
          <span className="font-mono text-[9px] uppercase tracking-widest font-black text-primary">
            Badge Unlocked
          </span>
        </div>
        <p className="font-black text-sm text-text dark:text-[#f0ebe2] break-words">
          {badge.name}
        </p>
        <p className="font-bold text-[11px] text-muted dark:text-[#c4bbae] leading-snug mt-0.5 line-clamp-2">
          {badge.desc}
        </p>
      </div>

      {/* Close button */}
      <button
        type="button"
        aria-label="Dismiss badge notification"
        onClick={(e) => {
          e.stopPropagation();
          dismiss();
        }}
        className="flex-shrink-0 p-1 rounded-lg border-2 border-black/20 hover:border-black hover:bg-surface-low transition-all dark:border-[#2e2924] dark:hover:border-[#c4bbae]"
      >
        <X size={12} />
      </button>
    </div>
  );
}

interface BadgeToastContainerProps {
  toasts: BadgeToastData[];
  onDismiss: (id: string) => void;
}

export function BadgeToastContainer({
  toasts,
  onDismiss,
}: BadgeToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Badge notifications"
      className={`
        fixed bottom-4 right-4 z-50
        flex flex-col-reverse gap-3
        w-[calc(100vw-2rem)] max-w-xs
        pointer-events-none
        sm:bottom-6 sm:right-6
      `}
    >
      {toasts.map((badge) => (
        <div key={badge.id} className="pointer-events-auto">
          <BadgeToast badge={badge} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
