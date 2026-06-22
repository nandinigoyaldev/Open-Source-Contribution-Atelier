import { Outlet } from "react-router-dom";
import { Navigation } from "./Navigation";
import { BadgeToastNotifier } from "../ui/BadgeToastNotifier";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-surface text-text dark:bg-transparent dark:text-[#f0ebe2]">
      <Navigation />
      <main className="lg:pl-[300px]">
        <div className="px-4 pb-10 pt-24 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </div>
      </main>
      <BadgeToastNotifier />
    </div>
  );
}
