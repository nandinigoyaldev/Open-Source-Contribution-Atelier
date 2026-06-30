import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import { useAuth } from "../../features/auth/AuthContext";
import { Trash2, AlertTriangle, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function DeleteAccountModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [confirmText, setConfirmText] = useState("");
  const { logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const deleteAccountMutation = useMutation({
    mutationFn: () => fetchApi("/auth/users/me/delete/", { method: "DELETE" }),
    onSuccess: () => {
      logout();
      queryClient.clear();
      navigate("/");
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-3xl border-4 border-black p-8 max-w-md w-full shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] relative animate-in fade-in zoom-in duration-200">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-full transition-colors"
        >
          <X className="w-6 h-6" />
        </button>

        <div className="flex flex-col items-center text-center space-y-4">
          <div className="bg-red-100 p-4 rounded-full border-2 border-red-500">
            <AlertTriangle className="w-10 h-10 text-red-500" />
          </div>

          <h2 className="text-2xl font-black uppercase tracking-tight text-red-600">
            Delete Account?
          </h2>

          <p className="font-bold text-gray-700">
            This action is permanent and cannot be undone.
          </p>

          <div className="bg-orange-50 border-2 border-orange-200 p-4 rounded-xl text-sm text-left text-gray-800 font-medium space-y-2 w-full">
            <p>
              <strong>What happens when you delete:</strong>
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                All personal data (PII), private notes, and progress will be
                permanently erased.
              </li>
              <li>Your certificates will become invalid.</li>
              <li>
                Public contributions (comments, chat messages) will remain but
                will be assigned to an "Anonymous Contributor" to preserve
                context.
              </li>
            </ul>
          </div>

          <div className="w-full pt-4 space-y-2">
            <label className="block text-sm font-bold text-gray-700 text-left">
              Type <span className="text-red-500 font-black">DELETE</span> to
              confirm:
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-300 rounded-xl font-bold uppercase placeholder:normal-case focus:border-red-500 focus:outline-none focus:ring-4 focus:ring-red-500/20 transition-all"
              placeholder="DELETE"
            />
          </div>

          <div className="flex gap-3 w-full pt-4">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-3 border-2 border-black rounded-xl font-black uppercase hover:bg-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteAccountMutation.mutate()}
              disabled={
                confirmText !== "DELETE" || deleteAccountMutation.isPending
              }
              className="flex-1 px-4 py-3 bg-red-500 text-white border-2 border-black rounded-xl font-black uppercase hover:bg-red-600 hover:-translate-y-1 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] disabled:opacity-50 disabled:hover:translate-y-0 disabled:shadow-none transition-all flex justify-center items-center gap-2"
            >
              <Trash2 className="w-5 h-5" />
              {deleteAccountMutation.isPending ? "Deleting..." : "Delete"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
