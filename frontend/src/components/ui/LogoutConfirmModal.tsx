import React, { useEffect } from "react";
import { createPortal } from "react-dom";

type Props = {
  open: boolean;
  title?: string;
  description?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function LogoutConfirmModal({
  open,
  title = "Confirm Logout",
  description = "Are you sure you want to logout?",
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if (e.key === "Enter") onConfirm();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel, onConfirm]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      aria-hidden={!open}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="logout-modal-title"
        className="bg-white p-6 border-4 border-black max-w-sm w-full shadow-lg"
      >
        <h2 id="logout-modal-title" className="font-bold text-lg mb-2">
          {title}
        </h2>
        <p className="mb-4">{description}</p>

        <div className="flex gap-3 justify-end">
          <button
            type="button"
            className="px-3 py-1 border-2 border-black text-sm bg-white hover:bg-gray-100"
            onClick={onCancel}
            data-testid="cancel-button"
          >
            Cancel
          </button>

          <button
            type="button"
            className="px-3 py-1 border-2 border-black text-sm bg-black text-white font-bold"
            onClick={onConfirm}
            data-testid="confirm-button"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
