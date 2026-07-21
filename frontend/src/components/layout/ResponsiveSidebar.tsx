import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import React, { useState, useEffect } from "react";

interface ResponsiveSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  children: React.ReactNode;
}

export function ResponsiveSidebar({
  isOpen,
  onClose,
  title,
  children,
}: ResponsiveSidebarProps) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  if (!isMobile) {
    return (
      <aside className="relative h-full w-[320px] border-r-4 border-black bg-white dark:bg-[#151411] dark:border-[#2e2924] overflow-y-auto p-6 flex-shrink-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-black uppercase flex items-center gap-2">
            {title}
          </h2>
        </div>
        {children}
      </aside>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[90] bg-black/40"
          />
          <motion.aside
            drag="x"
            dragConstraints={{ left: -300, right: 0 }}
            dragElastic={{ left: 0.05, right: 0.5 }}
            onDragEnd={(_, info) => {
              if (info.offset.x < -80) {
                onClose();
              }
            }}
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 250 }}
            className="fixed top-0 left-0 h-full w-[300px] border-r-4 border-black bg-white dark:bg-[#151411] dark:border-[#2e2924] overflow-y-auto p-6 z-[100] pt-6"
          >
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-black uppercase flex items-center gap-2">
                {title}
              </h2>
              <button
                onClick={onClose}
                aria-label="Close outline"
                className="border-2 border-black p-1 rounded-lg dark:border-[#2e2924] dark:text-[#f0ebe2]"
              >
                <X size={16} />
              </button>
            </div>
            {children}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

export default ResponsiveSidebar;
