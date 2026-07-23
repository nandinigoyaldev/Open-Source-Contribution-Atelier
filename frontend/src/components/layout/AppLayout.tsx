import { useEffect } from "react";
import { useLocation, Outlet, useNavigate } from "react-router-dom";
import { Navigation } from "./Navigation";
import { MobileBottomNav } from "./MobileBottomNav";
import { BadgeToastNotifier } from "../ui/BadgeToastNotifier";
import { SessionTracker } from "../ui/SessionTracker";
import { useAuth } from "../../features/auth/AuthContext";

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
      <a
        href="#main-content"
        className="
          sr-only
          focus:not-sr-only
          focus:absolute
          focus:top-4
          focus:left-4
          focus:z-[9999]
          focus:px-4
          focus:py-2
          focus:rounded
          focus:bg-red-600
          focus:text-white
        "
        onClick={(e) => {
          e.preventDefault();
          const mainContent = document.getElementById("main-content");
          mainContent?.focus();

          e.currentTarget.blur();
        }}
      >
        Skip to main content
      </a>

      <div className="min-h-screen bg-surface text-text dark:bg-[#0a0a0f] dark:text-[#f0ebe2]">
        {!location.pathname.startsWith("/lessons/") && <Navigation />}
        <main
          id="main-content"
          tabIndex={-1}
          className={
            location.pathname.startsWith("/lessons/")
              ? "w-full min-h-screen"
              : "lg:pl-[240px]"
          }
        >
          <div
            className={
              location.pathname.startsWith("/lessons/")
                ? "w-full h-screen overflow-hidden"
                : "px-4 pb-24 pt-24 sm:px-6 sm:pb-28 lg:px-8 lg:pb-10"
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
