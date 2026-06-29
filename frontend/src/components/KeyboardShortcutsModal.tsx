import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Keyboard, X } from "lucide-react";
import { useFocusTrap } from "../hooks/useFocusTrap";

interface ShortcutRow {
  category: string;
  keys: string[];
  description: string;
}

const shortcuts: ShortcutRow[] = [
  // Global
  {
    category: "Global",
    keys: ["⌘ K", "Ctrl K"],
    description: "Toggle Command Palette",
  },
  {
    category: "Global",
    keys: ["?"],
    description: "Toggle this Keyboard Shortcuts Help modal",
  },
  {
    category: "Global / Modals",
    keys: ["Esc"],
    description: "Close active modal or overlay",
  },
  // Command Palette
  {
    category: "Command Palette",
    keys: ["↑", "↓"],
    description: "Navigate through matching items",
  },
  {
    category: "Command Palette",
    keys: ["Enter"],
    description: "Select highlighted item",
  },
  // Sandbox Terminal
  {
    category: "Git Sandbox",
    keys: ["⌘ Enter", "Ctrl Enter"],
    description: "Submit command in lesson check prompt",
  },
  {
    category: "Git Sandbox",
    keys: ["↑", "↓"],
    description: "Traverse shell command history inside prompt input",
  },
  {
    category: "Git Sandbox (Nano)",
    keys: ["Ctrl X"],
    description: "Save file content and exit editor",
  },
  {
    category: "Git Sandbox (Nano)",
    keys: ["Ctrl C"],
    description: "Cancel editing and exit editor",
  },
  // Chat Room
  {
    category: "Chat Room",
    keys: ["Enter"],
    description: "Send typed message (without holding Shift)",
  },
  {
    category: "Chat Room",
    keys: ["Shift Enter"],
    description: "Insert new line in input area",
  },
];

export const KeyboardShortcutsModal: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  useFocusTrap(modalRef, isOpen);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check if target is an input, textarea, or contentEditable element
      const activeEl = document.activeElement;
      const isInput =
        activeEl &&
        (activeEl.tagName === "INPUT" ||
          activeEl.tagName === "TEXTAREA" ||
          activeEl.getAttribute("contenteditable") === "true");

      if (isInput) return;

      if (e.key === "?") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />

          {/* Modal Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.15 }}
            ref={modalRef}
            className="relative w-full max-w-2xl bg-[#0f0e0c] border-4 border-black rounded-2xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] overflow-hidden flex flex-col focus:outline-none z-10"
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-modal-title"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b-4 border-black bg-[#151411]">
              <div className="flex items-center gap-3">
                <Keyboard className="w-6 h-6 text-[#FFCC00] flex-shrink-0" />
                <h2
                  id="shortcuts-modal-title"
                  className="font-black text-xl tracking-tight text-white uppercase"
                >
                  Keyboard Shortcuts
                </h2>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-md border-2 border-transparent hover:border-black bg-transparent text-[#6b5a49] hover:text-[#f0ebe2] hover:bg-[#2e2924] transition-all"
                aria-label="Close shortcuts modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="flex-1 p-6 overflow-y-auto bg-[#0f0e0c] space-y-4 max-h-[65vh]">
              <p className="text-sm font-bold text-[#c4bbae]">
                Atelier workspace active keyboard shortcuts:
              </p>

              {/* Shortcuts Table */}
              <div className="border-4 border-black bg-[#151411] rounded-xl overflow-hidden shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-black border-b-4 border-black text-[#FFCC00] text-xs font-mono uppercase tracking-wider">
                      <th className="px-4 py-3">Context</th>
                      <th className="px-4 py-3">Shortcut keys</th>
                      <th className="px-4 py-3">Action description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shortcuts.map((shortcut, index) => (
                      <tr
                        key={index}
                        className="border-b-2 border-black/60 hover:bg-[#1f1c18]/50 text-[#f0ebe2] text-sm font-bold transition-colors"
                      >
                        <td className="px-4 py-3 text-xs font-mono text-[#c4bbae]">
                          {shortcut.category}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="flex flex-wrap gap-1.5">
                            {shortcut.keys.map((k, kIdx) => (
                              <React.Fragment key={kIdx}>
                                {kIdx > 0 && (
                                  <span className="text-[#6b5a49] self-center">
                                    or
                                  </span>
                                )}
                                <kbd className="inline-block px-2.5 py-1 bg-black text-[#FFCC00] font-mono text-xs rounded border-2 border-[#2e2924] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] select-none">
                                  {k}
                                </kbd>
                              </React.Fragment>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-[#f0ebe2]">
                          {shortcut.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t-4 border-black bg-[#151411] text-xs text-[#6b5a49] font-mono flex justify-between items-center">
              <span>
                Press{" "}
                <kbd className="bg-black rounded border border-[#2e2924] px-1 py-0.5 text-[#f0ebe2]">
                  Esc
                </kbd>{" "}
                or click outside to close
              </span>
              <span>The Maintainer Atelier</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
