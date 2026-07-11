import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import api from "../../api";
import toast from "react-hot-toast";

type Props = {
  open: boolean;
  onClose: () => void;
  urlPath?: string;
};

export default function ReportIssueModal({
  open,
  onClose,
  urlPath = window.location.pathname,
}: Props) {
  const modalRef = useRef<HTMLDivElement>(null);
  useFocusTrap(modalRef, open);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [issueType, setIssueType] = useState("Bug");
  const [image, setImage] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      // Reset form
      setTitle("");
      setDescription("");
      setIssueType("Bug");
      setImage(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !description) return;

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append("title", title);
    formData.append("description", description);
    formData.append("issue_type", issueType);
    formData.append("url_path", urlPath);
    if (image) {
      formData.append("image", image);
    }

    try {
      await api.post("/issues/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Issue reported successfully. Thank you!");
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch {
      toast.error("Failed to submit issue. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!open) return null;

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        aria-hidden={!open}
      >
        <div
          ref={modalRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="report-issue-modal-title"
          className="bg-white p-6 border-4 border-black max-w-lg w-full rounded-2xl shadow-[6px_6px_0px_0px_#000000] flex flex-col max-h-[90vh]"
        >
          <div className="flex justify-between items-center mb-4">
            <h2 id="report-issue-modal-title" className="font-bold text-xl">
              Report an Issue
            </h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-black"
            >
              ✕
            </button>
          </div>

          <form
            onSubmit={handleSubmit}
            className="flex flex-col gap-4 overflow-y-auto pr-2"
          >
            <div>
              <label className="block text-sm font-bold mb-1">Issue Type</label>
              <select
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                className="w-full p-2 border-2 border-black rounded-lg focus:outline-none focus:ring-2 focus:ring-black"
              >
                <option value="Bug">Bug</option>
                <option value="Content">Incorrect Content / Typo</option>
                <option value="UI">UI/UX Issue</option>
                <option value="Sandbox">Coding Sandbox Issue</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-bold mb-1">Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full p-2 border-2 border-black rounded-lg focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="Brief summary of the issue"
              />
            </div>

            <div>
              <label className="block text-sm font-bold mb-1">
                Description
              </label>
              <textarea
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full p-2 border-2 border-black rounded-lg focus:outline-none focus:ring-2 focus:ring-black min-h-[100px] resize-y"
                placeholder="Detailed steps to reproduce the issue..."
              />
            </div>

            <div>
              <label className="block text-sm font-bold mb-1">
                Attach Image (Optional)
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    setImage(e.target.files[0]);
                  }
                }}
                className="w-full p-2 border-2 border-gray-300 border-dashed rounded-lg focus:outline-none text-sm"
              />
            </div>

            <div className="flex gap-3 justify-end mt-4">
              <button
                type="button"
                className="px-4 py-2 rounded-lg border-2 border-black text-sm font-bold bg-white hover:bg-gray-100 shadow-[3px_3px_0px_0px_#000] active:shadow-none active:translate-x-[3px] active:translate-y-[3px] transition-all"
                onClick={onClose}
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 rounded-lg border-2 border-black text-sm font-black bg-[#b5e8ff] text-black shadow-[3px_3px_0px_0px_#000] active:shadow-none active:translate-x-[3px] active:translate-y-[3px] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? "Submitting..." : "Submit Report"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>,
    document.body,
  );
}
