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
        className="rounded-lg bg-[#ffb5e8] px-3 py-2 text-xs font-black text-black border-2 border-black shadow-card-sm hover:-translate-y-0.5 hover:shadow-card active:translate-y-0.5 active:shadow-card-sm transition-all cursor-pointer uppercase"
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
