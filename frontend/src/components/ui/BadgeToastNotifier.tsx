import { useAuth } from "../../features/auth/AuthContext";
import { BadgeToastContainer } from "./BadgeToast";
import { useBadgeToast } from "../../hooks/useBadgeToast";
import { useEarnedBadges } from "../../hooks/useEarnedBadges";
import { BADGES } from "../../constants/badges";

export function BadgeToastNotifier() {
  const { user } = useAuth();
  const { earnedBadges, isLessonsLoading, curriculumData } = useEarnedBadges();

  // Wait for lessons and curriculum data to load before checking for new badges.
  const isDataReady = !isLessonsLoading && curriculumData.length > 0;

  const { toasts, dismissToast } = useBadgeToast(
    earnedBadges,
    BADGES,
    isDataReady,
  );

  if (!user || user.is_staff) return null;

  return <BadgeToastContainer toasts={toasts} onDismiss={dismissToast} />;
}
