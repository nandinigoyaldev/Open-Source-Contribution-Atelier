import { useEffect } from "react";
import { useLocation, Outlet, useNavigate } from "react-router-dom";
import { Navigation } from "./Navigation";
import { SideNav } from "./SideNav";
import { MobileBottomNav } from "./MobileBottomNav";
import { BadgeToastNotifier } from "../ui/BadgeToastNotifier";
import { SessionTracker } from "../ui/SessionTracker";
import { useAuth } from "../../features/auth/AuthContext";
import { SkipLink } from "../ui/SkipLink";

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isLessonPage = location.pathname.startsWith("/lessons/");

  useEffect(() => {
    if (user && sessionStorage.getItem("justLoggedIn") === "true") {
      sessionStorage.removeItem("justLoggedIn");
      if (!user.bio) {
        navigate("/profile");
      }
    }
  }, [user, navigate]);

  return (
    <>
      <SkipLink />

      <div className="min-h-screen bg-surface text-text dark:bg-[#0a0a0f] dark:text-[#f0ebe2] overflow-x-hidden">
        {/* Top bar: always visible except on lesson pages */}
        {!isLessonPage && <Navigation />}

        <div className="flex min-h-[calc(100vh-3.5rem)]">
          {/* Side nav: desktop only, not on lesson pages */}
          {!isLessonPage && <SideNav />}

          <main
            id="main-content"
            tabIndex={-1}
            className={`flex-1 min-w-0 ${
              isLessonPage
                ? "w-full min-h-screen"
                : "pt-4 min-h-screen max-w-full overflow-x-hidden px-3 sm:px-6 lg:px-8 pb-20 sm:pb-24 lg:pb-10"
            }`}
          >
            <div
              className={
                isLessonPage
                  ? "w-full h-screen overflow-hidden"
                  : "max-w-7xl mx-auto w-full min-w-0"
              }
            >
              <Outlet />
            </div>
          </main>
        </div>

        {!isLessonPage && <MobileBottomNav />}
        <BadgeToastNotifier />
        {!isLessonPage && <SessionTracker />}
      </div>
    </>
  );
}

export default AppLayout;
