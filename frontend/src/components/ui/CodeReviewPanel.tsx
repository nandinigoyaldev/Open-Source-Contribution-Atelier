import React, { useState } from "react";
import { CodeReviewThread } from "../../lib/api";
import { X, MessageSquare, Check, Send } from "lucide-react";

interface CodeReviewPanelProps {
  activeLine: number | null;
  threads: CodeReviewThread[];
  onAddComment: (line: number, content: string, threadId?: string) => void;
  onResolveThread: (threadId: string) => void;
  onClose: () => void;
}

export function CodeReviewPanel({
  activeLine,
  threads,
  onAddComment,
  onResolveThread,
  onClose,
}: CodeReviewPanelProps) {
  const [newComment, setNewComment] = useState("");

  if (activeLine === null) return null;

  // Find the active thread for this line
  const activeThread = threads.find(
    (t) => t.line_number === activeLine && !t.is_resolved
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    onAddComment(activeLine, newComment, activeThread?.id);
    setNewComment("");
  };

  return (
    <div className="w-80 h-full bg-white dark:bg-[#1a1a1a] border-l border-gray-200 dark:border-gray-800 flex flex-col shadow-lg z-10">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
        <h3 className="font-bold flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-blue-500" />
          Line {activeLine}
        </h3>
        <div className="flex items-center gap-2">
          {activeThread && (
            <button
              onClick={() => onResolveThread(activeThread.id)}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-green-500 transition-colors"
              title="Resolve Thread"
            >
              <Check className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!activeThread ? (
          <div className="text-sm text-gray-500 italic text-center mt-10">
            No active comments on line {activeLine}.<br />
            Start a discussion below!
          </div>
        ) : (
          activeThread.comments.map((comment) => (
            <div key={comment.id} className="bg-gray-50 dark:bg-[#252525] p-3 rounded-lg border border-gray-100 dark:border-gray-800">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-sm">
                  {comment.user.username}
                </span>
                <span className="text-xs text-gray-500">
                  {new Date(comment.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {comment.content}
              </p>
            </div>
          ))
        )}
      </div>

      <div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-[#1e1e1e]">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Type a comment..."
            className="flex-1 bg-white dark:bg-[#252525] border border-gray-200 dark:border-gray-700 rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-10 min-h-[40px] max-h-32"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <button
            type="submit"
            disabled={!newComment.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white p-2 rounded-md flex items-center justify-center transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
