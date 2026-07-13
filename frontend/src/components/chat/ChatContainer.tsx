import { useEffect, useRef } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import { useChat } from "../../hooks/useChat";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { TypingIndicator } from "./TypingIndicator";
import { SectionCard } from "../ui/SectionCard";

function getAccessToken(): string | null {
  try {
    return localStorage.getItem("accessToken");
  } catch {
    return null;
  }
}

export function ChatContainer() {
  const { user } = useAuth();
  const token = getAccessToken();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const roomId = "community";

  const {
    messages,
    typingUsers,
    onlineUsers,
    isConnected,
    sendMessage,
    onInputChange,
    onInputBlur,
    onInputSubmit,
  } = useChat({ roomId, token, username: user?.username });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUsers]);

  return (
    <section className="dark-card-depth rounded-[24px] border border-outline bg-surface-high/80 p-6 shadow-card backdrop-blur-xl dark:text-[#f0ebe2] flex flex-col h-[500px] min-h-0">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.24em] text-muted dark:text-[#d7cec0]">
        Real-time Chat
      </p>
      <h2 className="mt-2 text-2xl font-bold tracking-[-0.02em] text-text dark:text-[#fff8ef]">
        Community Chat
      </h2>
      <div className="flex-1 flex flex-col min-h-0 mt-4">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-black/10 dark:border-[#3a3a45]/30">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isConnected
                  ? "bg-green-500 shadow-sm shadow-green-500/50"
                  : "bg-red-500 shadow-sm shadow-red-500/50"
              }`}
            />
            <span className="text-xs font-bold text-muted dark:text-[#a0a0ab]">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>

          {onlineUsers && onlineUsers.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider font-black text-muted dark:text-[#a0a0ab]">
                {onlineUsers.length} Online
              </span>
              <div className="flex -space-x-1.5">
                {onlineUsers.slice(0, 5).map((u) => (
                  <img
                    key={u.user_id}
                    src={`https://github.com/${u.username}.png`}
                    alt={u.username}
                    title={u.username}
                    className="w-5 h-5 rounded-full border border-white dark:border-[#1f1c18]"
                  />
                ))}
                {onlineUsers.length > 5 && (
                  <div className="w-5 h-5 rounded-full bg-black text-white dark:bg-[#eef2f6] dark:text-black border border-white dark:border-[#1f1c18] flex items-center justify-center text-[8px] font-bold z-10">
                    +{onlineUsers.length - 5}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 space-y-3 px-1 mb-2 custom-scrollbar">
          {messages.length === 0 && (
            <p className="text-center text-sm text-muted py-8">
              No messages yet. Start the conversation!
            </p>
          )}
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg.message}
              username={msg.username}
              isOwn={msg.user_id === user?.id}
              timestamp={msg.timestamp || msg.created_at}
            />
          ))}

          <div ref={messagesEndRef} />
        </div>

        <TypingIndicator users={typingUsers} className="px-1 pb-1" />

        <ChatInput
          onSendMessage={sendMessage}
          onInputChange={onInputChange}
          onInputBlur={onInputBlur}
          onInputSubmit={onInputSubmit}
          disabled={!isConnected}
        />
      </div>
    </section>
  );
}
