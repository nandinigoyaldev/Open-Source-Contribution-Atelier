import { useEffect, useRef } from "react";
import { useAuth } from "../features/auth/AuthContext";
import { useChat } from "../hooks/useChat";
import { ChatMessage } from "../components/chat/ChatMessage";
import { ChatInput } from "../components/chat/ChatInput";
import { TypingIndicator } from "../components/chat/TypingIndicator";
import { SectionCard } from "../components/ui/SectionCard";

function getAccessToken(): string | null {
  try {
    return localStorage.getItem("accessToken");
  } catch {
    return null;
  }
}

export function ChatPage() {
  const { user } = useAuth();
  const token = getAccessToken();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const roomId = "general";

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

  return (
    <div className="pt-24 max-w-3xl mx-auto px-4 pb-12">
      <SectionCard
        eyebrow="Real-time Chat"
        title="Community Chat"
        className="flex flex-col h-[calc(100vh-12rem)]"
      >
        <div className="flex items-center gap-2 mb-4">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              isConnected ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-xs font-bold text-muted">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3 px-1">
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
              timestamp={msg.timestamp}
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
      </SectionCard>
    </div>
  );
}
