import React, { useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import LogoutConfirmModal from "../ui/LogoutConfirmModal";

export default function LogoutButtonWithConfirm() {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-400/10 menu-logout"
      >
        Logout
      </button>

      <LogoutConfirmModal
        open={open}
        onCancel={() => setOpen(false)}
        onConfirm={() => {
          setOpen(false);
          logout();
        }}
      />
    </>
  );
}
