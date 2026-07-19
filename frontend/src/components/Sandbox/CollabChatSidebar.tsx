import React, { useState, useRef, useEffect } from "react";
import { useChat } from "../../hooks/useChat";
import { getAccessToken } from "../../lib/authToken";

interface CollabChatSidebarProps {
  sessionId: string;
  username: string;
}

export function CollabChatSidebar({
  sessionId,
  username,
}: CollabChatSidebarProps) {
  const token = getAccessToken();
  // Route collab chat through a scoped room so it's isolated from global chat
  const roomId = `collab_${sessionId}`;

  const { messages, isConnected, sendMessage } = useChat({
    roomId,
    token,
    username,
  });

  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = draft.trim();
    if (!text) return;
    sendMessage(text);
    setDraft("");
  };

  return (
    <div className="flex h-full flex-col gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
      <div className="flex items-center justify-between text-xs text-white/50">
        <span className="font-semibold uppercase tracking-wide">
          Session Chat
        </span>
        <span
          className={`h-1.5 w-1.5 rounded-full ${isConnected ? "bg-green-400" : "bg-yellow-400"}`}
        />
      </div>

      {/* Message list */}
      <div className="flex flex-1 flex-col gap-1 overflow-y-auto text-sm">
        {messages.length === 0 && (
          <p className="mt-4 text-center text-white/30 italic">
            No messages yet
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className="flex flex-col">
            <span className="text-xs text-white/40">{m.username}</span>
            <span className="rounded bg-white/10 px-2 py-1 text-white/90">
              {m.message}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          id="collab-chat-input"
          className="flex-1 rounded border border-white/10 bg-white/10 px-2 py-1 text-sm text-white placeholder-white/30 outline-none focus:border-indigo-500"
          placeholder="Type a message…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          aria-label="Chat message input"
        />
        <button
          id="collab-chat-send-btn"
          onClick={handleSend}
          className="rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-indigo-500 active:scale-95"
          aria-label="Send message"
        >
          Send
        </button>
      </div>
    </div>
  );
}
