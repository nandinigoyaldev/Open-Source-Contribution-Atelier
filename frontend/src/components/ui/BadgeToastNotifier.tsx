import { useEffect, useRef } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import { BadgeToastContainer } from "./BadgeToast";
import { useNotifications } from "../../features/notifications/NotificationContext";
import { useTheme } from "../../context/ThemeContext";

export function BadgeToastNotifier() {
  const { user } = useAuth();
  const { toasts, dismissToast } = useNotifications();
  const { playAudioCue } = useTheme();
  
  // Track the previous toasts length context to ensure audio only fires on new alerts
  const previousLengthRef = useRef(toasts.length);

  useEffect(() => {
    if (toasts.length > previousLengthRef.current) {
      // Trigger the bright arpeggiated melodic sound cue for new badge pops
      playAudioCue("achievement");
    }
    previousLengthRef.current = toasts.length;
  }, [toasts, playAudioCue]);

  if (!user || user.is_staff) return null;

  return <BadgeToastContainer toasts={toasts as any} onDismiss={dismissToast} />;
}
