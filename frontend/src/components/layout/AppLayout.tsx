import { useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Navigation } from "./Navigation";
import { BadgeToastNotifier } from "../ui/BadgeToastNotifier";
import { ScrollToTop } from "../ui/ScrollToTop";

export function AppLayout() {
  const location = useLocation();
  const outlet = useOutlet();

  return (
    <div className="min-h-screen bg-surface text-text dark:bg-transparent dark:text-[#f0ebe2]">
      <Navigation />
      <main className="lg:pl-[300px]">
        <div className="px-4 pb-10 pt-24 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.25, ease: "easeOut" }}
              >
                {outlet}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </main>
      <BadgeToastNotifier />
      <ScrollToTop />
    </div>
  );
}
