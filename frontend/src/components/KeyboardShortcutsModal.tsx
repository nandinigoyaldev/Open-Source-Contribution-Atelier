import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Keyboard, X } from "lucide-react";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { isTypingTarget } from "../lib/accessibility";
import { ShortcutSettingsModal } from "../features/shortcuts/ShortcutSettingsModal";
import { ShortcutId, getShortcut } from "../features/shortcuts/registry";
import { useCustomShortcuts } from "../features/shortcuts/useCustomShortcuts";

interface StaticRow {
  category: string;
  keys: string[];
  description: string;
}

// Rows with an id come from the shortcut registry and show the user's keys.
// The rest are fixed keys that cannot be remapped.
const shortcuts: (ShortcutId | StaticRow)[] = [
  // Global
  "search.toggle",
  "help.toggle",
  {
    category: "Global / Modals",
    keys: ["Esc"],
    description: "Close active modal, panel, or overlay",
  },
  "nav.dashboard",
  // Lesson Navigation
  "lesson.next",
  "lesson.previous",
  "lesson.toggleSidebar",
  "lesson.toggleBookmark",
  "lesson.toggleNotes",
  "lesson.toggleHelp",
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
  "lesson.runCommand",
  {
    category: "Git Sandbox",
    keys: ["↑", "↓"],
    description: "Traverse shell command history inside prompt input",
  },
  "terminal.clear",
  "terminal.copy",
  "terminal.focusInput",
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
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const { labels, matches } = useCustomShortcuts();
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  useFocusTrap(modalRef, isOpen);

  const openModal = () => {
    triggerRef.current = document.activeElement as HTMLElement | null;
    setIsOpen(true);
  };

  const closeModal = () => {
    setIsOpen(false);
    // Explicitly restore focus to the element that triggered the modal
    if (triggerRef.current && typeof triggerRef.current.focus === "function") {
      triggerRef.current.focus();
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Inputs, textareas, and editable fields are never hijacked
      if (isTypingTarget(e)) return;

      if (matches(e, "help.toggle")) {
        e.preventDefault();
        if (isOpen) {
          closeModal();
        } else {
          openModal();
        }
      } else if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        closeModal();
      }
    };

    const handleCustomToggle = () => {
      if (isOpen) {
        closeModal();
      } else {
        openModal();
      }
    };

    const handleCustomOpen = () => openModal();
    const handleCustomClose = () => closeModal();

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("toggle-keyboard-shortcuts", handleCustomToggle);
    window.addEventListener("open-keyboard-shortcuts", handleCustomOpen);
    window.addEventListener("close-keyboard-shortcuts", handleCustomClose);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener(
        "toggle-keyboard-shortcuts",
        handleCustomToggle,
      );
      window.removeEventListener("open-keyboard-shortcuts", handleCustomOpen);
      window.removeEventListener("close-keyboard-shortcuts", handleCustomClose);
    };
  }, [isOpen, matches]);

  useEffect(() => {
    if (isOpen) {
      closeButtonRef.current?.focus();
    }
  }, [isOpen]);

  const rows = shortcuts.map((row) =>
    typeof row === "string" ? { ...getShortcut(row), keys: labels(row) } : row,
  );

  return (
    <>
      <ShortcutSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
      <AnimatePresence>
        {isOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop Overlay */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/80 backdrop-blur-sm"
              onClick={closeModal}
              data-testid="shortcuts-backdrop"
            />

            {/* Modal Container */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.15 }}
              ref={modalRef}
              className="relative w-full max-w-2xl bg-[#0f0e0c] border border-slate-700 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col focus:outline-none z-10"
              role="dialog"
              aria-modal="true"
              aria-labelledby="shortcuts-modal-title"
              aria-describedby="shortcuts-modal-desc"
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
                  ref={closeButtonRef}
                  onClick={closeModal}
                  className="p-1.5 rounded-md border-2 border-transparent hover:border-black bg-transparent text-[#6b5a49] hover:text-[#f0ebe2] hover:bg-[#2e2924] transition-all"
                  aria-label="Close shortcuts modal"
                  data-testid="close-shortcuts-button"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Content Body */}
              <div className="flex-1 p-6 overflow-y-auto bg-[#0f0e0c] space-y-4 max-h-[65vh]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p
                    id="shortcuts-modal-desc"
                    className="text-sm font-bold text-[#c4bbae]"
                  >
                    Atelier workspace active keyboard shortcuts:
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      closeModal();
                      setIsSettingsOpen(true);
                    }}
                    className="px-3 py-1.5 text-xs font-black rounded-md border-2 border-black bg-[#FFCC00] text-black hover:-translate-y-0.5 transition-all"
                  >
                    Customize shortcuts
                  </button>
                </div>

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
                      {rows.map((shortcut, index) => (
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
    </>
  );
};
