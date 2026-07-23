import React, { useState } from "react";
import { fetchApi } from "../../lib/api";

interface ReportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  contentType: "progress.peerreview";
  objectId: number;
}

export function ReportDialog({
  isOpen,
  onClose,
  contentType,
  objectId,
}: ReportDialogProps) {
  const [category, setCategory] = useState("SPAM");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      await fetchApi("/moderation/reports/", {
        method: "POST",
        body: JSON.stringify({
          content_type_model: contentType.split(".")[1],
          content_type_app: contentType.split(".")[0],
          object_id: objectId,
          category,
          description,
        }),
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Failed to submit report");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-surface dark:bg-[#1a1816] w-full max-w-md rounded-2xl border-4 border-black p-6 shadow-card text-black dark:text-white">
        <h2 className="text-2xl font-black mb-4 uppercase text-black dark:text-white">
          Report Content
        </h2>

        {success ? (
          <div>
            <p className="mb-6 font-bold text-green-600">
              Report submitted successfully. Thank you for keeping the community
              safe!
            </p>
            <button
              onClick={onClose}
              className="w-full py-3 bg-black text-white dark:bg-white dark:text-black font-bold rounded-lg border-2 border-black dark:border-white hover:-translate-y-1 transition-all"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-100 text-red-800 border-2 border-red-500 rounded-lg font-bold text-sm">
                {error}
              </div>
            )}
            <div>
              <label className="block font-bold mb-2">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-4 py-2 border-2 border-black rounded-lg focus:ring-2 focus:ring-primary dark:bg-black dark:border-[#2e2924]"
              >
                <option value="SPAM">Spam</option>
                <option value="ABUSIVE">Abusive Language</option>
                <option value="HARASSMENT">Harassment</option>
                <option value="MISINFORMATION">Misinformation</option>
                <option value="PLAGIARISM">Plagiarism</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div>
              <label className="block font-bold mb-2">
                Description (Optional)
              </label>
              <textarea
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Provide additional details..."
                className="w-full px-4 py-2 border-2 border-black rounded-lg focus:ring-2 focus:ring-primary dark:bg-black dark:border-[#2e2924]"
              />
            </div>
            <div className="flex gap-4 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-3 bg-surface-low border-2 border-black dark:border-white rounded-lg font-bold hover:bg-black/5 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 py-3 bg-red-500 text-white font-black uppercase border-2 border-black rounded-lg hover:-translate-y-1 shadow-card transition-all disabled:opacity-50"
              >
                {isSubmitting ? "Submitting..." : "Report"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
