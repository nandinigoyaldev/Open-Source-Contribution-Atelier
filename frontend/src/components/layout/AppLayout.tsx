import { useEffect } from "react";
import { useLocation, Outlet, useNavigate } from "react-router-dom";
import { Navigation } from "./Navigation";
import { MobileBottomNav } from "./MobileBottomNav";
import { BadgeToastNotifier } from "../ui/BadgeToastNotifier";
import { SessionTracker } from "../ui/SessionTracker";
import { useAuth } from "../../features/auth/AuthContext";
import { SkipLink } from "../ui/SkipLink";

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

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
        {!location.pathname.startsWith("/lessons/") && <Navigation />}
        <main
          id="main-content"
          tabIndex={-1}
          className={
            location.pathname.startsWith("/lessons/")
              ? "w-full min-h-screen"
              : "pt-16 min-h-screen max-w-full overflow-x-hidden"
          }
        >
          <div
            className={
              location.pathname.startsWith("/lessons/")
                ? "w-full h-screen overflow-hidden"
                : "px-3 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8 max-w-7xl mx-auto w-full min-w-0 pb-20 sm:pb-24 lg:pb-10"
            }
          >
            <Outlet />
          </div>
        </main>
        {!location.pathname.startsWith("/lessons/") && <MobileBottomNav />}
        <BadgeToastNotifier />
        {!location.pathname.startsWith("/lessons/") && <SessionTracker />}
      </div>
    </>
  );
}
