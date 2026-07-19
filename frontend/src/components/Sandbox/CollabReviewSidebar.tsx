import React, { useState } from "react";
import { MessageSquare, CheckCircle, Plus } from "lucide-react";
import type { CodeReviewThread } from "../../lib/api";

interface CollabReviewSidebarProps {
  sessionId: string;
  username: string;
  selectedLine: number | null;
  threads: CodeReviewThread[];
  onAddComment: (line: number, content: string, threadId?: string) => void;
  onResolveThread: (threadId: string) => void;
}

export function CollabReviewSidebar({
  sessionId,
  username,
  selectedLine,
  threads,
  onAddComment,
  onResolveThread,
}: CollabReviewSidebarProps) {
  const [commentInput, setCommentInput] = useState("");
  const [replyInputs, setReplyInputs] = useState<Record<string, string>>({});

  const handleAddThread = () => {
    if (selectedLine === null || !commentInput.trim()) return;
    onAddComment(selectedLine, commentInput.trim());
    setCommentInput("");
  };

  const handleAddReply = (threadId: string, line: number) => {
    const replyText = replyInputs[threadId]?.trim();
    if (!replyText) return;
    onAddComment(line, replyText, threadId);
    setReplyInputs((prev) => ({ ...prev, [threadId]: "" }));
  };

  // Group threads into resolved vs active
  const activeThreads = threads.filter((t) => !t.is_resolved);
  const resolvedThreads = threads.filter((t) => t.is_resolved);

  return (
    <div className="flex h-full flex-col gap-3 rounded-lg border border-white/10 bg-white/5 p-3 text-sm">
      <div className="flex items-center justify-between text-xs text-white/50 border-b border-white/10 pb-2">
        <span className="font-semibold uppercase tracking-wide flex items-center gap-1">
          <MessageSquare className="w-3.5 h-3.5" /> Code Reviews
        </span>
      </div>

      {/* Selected Line Context & Add Thread */}
      <div className="rounded-md border border-white/10 bg-white/5 p-2">
        {selectedLine !== null ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-indigo-400">
              Active line: Line {selectedLine}
            </p>
            {activeThreads.some((t) => t.line_number === selectedLine) ? (
              <p className="text-xs text-white/50">
                A review thread is already active on this line. Use the list
                below to reply.
              </p>
            ) : (
              <div className="space-y-2">
                <textarea
                  id="collab-review-new-input"
                  rows={2}
                  className="w-full rounded border border-white/10 bg-white/5 p-2 text-xs text-white outline-none focus:border-indigo-500 placeholder-white/30 resize-none"
                  placeholder="Start a new review thread on this line..."
                  value={commentInput}
                  onChange={(e) => setCommentInput(e.target.value)}
                />
                <button
                  id="collab-review-create-btn"
                  onClick={handleAddThread}
                  className="w-full flex items-center justify-center gap-1 rounded bg-indigo-600 py-1 text-xs font-semibold text-white transition hover:bg-indigo-500"
                >
                  <Plus className="w-3.5 h-3.5" /> Start Thread
                </button>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-white/40 text-center py-2">
            Click on a line in the editor to start a new review thread.
          </p>
        )}
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {activeThreads.length === 0 && (
          <p className="text-center text-white/30 italic text-xs py-4">
            No active review threads
          </p>
        )}

        {/* Active Threads */}
        {activeThreads.map((thread) => (
          <div
            key={thread.id}
            id={`review-thread-${thread.id}`}
            className="rounded-md border border-white/10 bg-white/5 p-3 space-y-2"
          >
            <div className="flex items-center justify-between border-b border-white/5 pb-1">
              <span className="text-xs font-bold text-white/60">
                Line {thread.line_number}
              </span>
              <button
                id={`resolve-btn-${thread.id}`}
                onClick={() => onResolveThread(thread.id)}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium border border-green-500/30 bg-green-500/10 text-green-400 transition hover:bg-green-500/20"
                title="Resolve thread"
              >
                <CheckCircle className="w-3.5 h-3.5" /> Resolve
              </button>
            </div>

            {/* Comments stack */}
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {thread.comments?.map((comment) => (
                <div key={comment.id} className="text-xs space-y-0.5">
                  <div className="flex items-center justify-between text-white/40 text-[10px]">
                    <span className="font-semibold text-white/60">
                      {comment.user.username}
                    </span>
                    <span>
                      {new Date(comment.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-white/80 bg-white/5 rounded px-2 py-1 leading-relaxed break-words">
                    {comment.content}
                  </p>
                </div>
              ))}
            </div>

            {/* Reply Input */}
            <div className="flex gap-1.5 pt-2 border-t border-white/5">
              <input
                id={`reply-input-${thread.id}`}
                type="text"
                className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white placeholder-white/30 outline-none focus:border-indigo-500"
                placeholder="Reply to thread..."
                value={replyInputs[thread.id] || ""}
                onChange={(e) =>
                  setReplyInputs((prev) => ({
                    ...prev,
                    [thread.id]: e.target.value,
                  }))
                }
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  handleAddReply(thread.id, thread.line_number)
                }
              />
              <button
                id={`reply-send-${thread.id}`}
                onClick={() => handleAddReply(thread.id, thread.line_number)}
                className="rounded bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white transition hover:bg-indigo-500"
              >
                Send
              </button>
            </div>
          </div>
        ))}

        {/* Resolved Threads Accordion / List if any */}
        {resolvedThreads.length > 0 && (
          <div className="pt-2 border-t border-white/10">
            <p className="text-xs font-bold text-white/30 mb-2">
              Resolved ({resolvedThreads.length})
            </p>
            <div className="space-y-1.5 opacity-55">
              {resolvedThreads.map((thread) => (
                <div
                  key={thread.id}
                  className="flex items-center justify-between rounded bg-white/5 px-2.5 py-1.5 text-xs text-white/60"
                >
                  <span>Line {thread.line_number}</span>
                  <span className="text-[10px] text-green-400">Resolved</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
