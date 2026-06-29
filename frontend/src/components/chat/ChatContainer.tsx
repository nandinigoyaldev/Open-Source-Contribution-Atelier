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
    <SectionCard
      eyebrow="Real-time Chat"
      title="Community Chat"
      className="flex flex-col h-[500px]"
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

      <div className="flex-1 overflow-y-auto space-y-3 px-1 mb-2">
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
    </SectionCard>
  );
}
