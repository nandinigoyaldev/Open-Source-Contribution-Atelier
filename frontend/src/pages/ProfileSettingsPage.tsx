import React, { useState } from "react";
import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";
import { ShortcutSettingsModal } from "../features/shortcuts/ShortcutSettingsModal";

export function ProfileSettingsPage() {
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white uppercase mb-2">
          Profile Settings
        </h1>
        <p className="text-lg font-bold text-gray-600 dark:text-gray-300">
          Update your display name, bio, avatar and timezone.
        </p>
      </div>
      <ProfileSettingsForm />
      <section
        aria-labelledby="keyboard-shortcuts-heading"
        className="mt-8 rounded-2xl border-4 border-black p-6 dark:border-[#2e2924]"
      >
        <h2
          id="keyboard-shortcuts-heading"
          className="text-xl font-black uppercase text-black dark:text-white"
        >
          Keyboard shortcuts
        </h2>
        <p className="mt-1 mb-4 text-sm font-bold text-gray-600 dark:text-gray-300">
          Remap the keys used on lessons, search and the sandbox terminal.
        </p>
        <button
          type="button"
          onClick={() => setIsShortcutsOpen(true)}
          className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-black font-bold text-sm rounded-xl border-2 border-black shadow-card-sm"
        >
          Customize shortcuts
        </button>
      </section>
      <ShortcutSettingsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />
    </div>
  );
}

export default ProfileSettingsPage;
