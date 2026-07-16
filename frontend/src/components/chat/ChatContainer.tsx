import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import { useChat } from "../../hooks/useChat";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { TypingIndicator } from "./TypingIndicator";
import { SectionCard } from "../ui/SectionCard";
import { getAccessToken } from "../../lib/authToken";
import { ChatThreadPanel } from "./chatthreadpanel";

export function ChatContainer() {
  const { user } = useAuth();
  const token = getAccessToken();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [activeParentId, setActiveParentId] = useState<string | number | null>(
    null,
  );

  const roomId = "community";

  const {
    messages,
    typingUsers,
    isConnected,
    sendMessage,
    onInputChange,
    onInputBlur,
    onInputSubmit,
  } = useChat({ roomId, token, username: user?.username });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUsers]);

  const topLevelMessages = messages.filter((m) => !m.parent_id);
  const threadMessages = activeParentId
    ? messages.filter((m) => m.parent_id === activeParentId)
    : [];
  const activeParentMessage = activeParentId
    ? messages.find((m) => m.id === activeParentId)
    : null;

  return (
    <SectionCard
      eyebrow="Real-time Chat"
      title="Community Chat"
      className="flex flex-col"
    >
      <div className="flex h-[500px] overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm mt-4">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="flex items-center gap-2 mb-4">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-xs font-bold text-muted uppercase tracking-wider">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 px-1 mb-3 pr-2 styled-scrollbar">
            {topLevelMessages.length === 0 && (
              <p className="text-center text-sm text-muted py-8">
                No messages yet. Start the conversation!
              </p>
            )}
            {topLevelMessages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg.message}
                username={msg.username}
                isOwn={msg.user_id === user?.id}
                timestamp={msg.timestamp || msg.created_at}
                replyCount={
                  messages.filter((m) => m.parent_id === msg.id).length
                }
                onReply={() => setActiveParentId(msg.id)}
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

        {/* Thread Panel */}
        {activeParentMessage && (
          <ChatThreadPanel
            parentMessage={activeParentMessage}
            messages={threadMessages}
            isConnected={isConnected}
            onSendMessage={sendMessage}
            onClose={() => setActiveParentId(null)}
          />
        )}
      </div>
    </SectionCard>
  );
}
