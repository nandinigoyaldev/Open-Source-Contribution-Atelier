import { useEffect } from "react";
import { useLocation, Outlet, useNavigate } from "react-router-dom";
import { Navigation } from "./Navigation";
import { BadgeToastNotifier } from "../ui/BadgeToastNotifier";
import { ScrollToTop } from "../ui/ScrollToTop";
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

      <div className="min-h-screen bg-surface text-text dark:bg-transparent dark:text-[#f0ebe2]">
        <Navigation />
        <main id="main-content" tabIndex={-1} className="lg:pl-[240px]">
          <div className="px-4 pb-10 pt-24 sm:px-6 lg:px-8">
              <Outlet />
          </div>
        </main>
        <BadgeToastNotifier />
        <ScrollToTop />
        <SessionTracker />
      </div>
    </>
  );
}
