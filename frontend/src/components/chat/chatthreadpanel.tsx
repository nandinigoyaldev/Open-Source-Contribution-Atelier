import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { ChatMessage as ChatMessageType } from "../../hooks/useChat";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { useAuth } from "../../features/auth/AuthContext";

type ChatThreadPanelProps = {
  parentMessage: ChatMessageType;
  messages: ChatMessageType[];
  isConnected: boolean;
  onSendMessage: (text: string, parentId?: number) => void;
  onClose: () => void;
};

export function ChatThreadPanel({
  parentMessage,
  messages,
  isConnected,
  onSendMessage,
  onClose,
}: ChatThreadPanelProps) {
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = (text: string) => {
    const pid =
      typeof parentMessage.id === "number"
        ? parentMessage.id
        : parseInt(parentMessage.id as string, 10);
    if (!isNaN(pid)) {
      onSendMessage(text, pid);
    }
  };

  return (
    <div className="flex flex-col h-full border-l border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 w-full md:w-[350px] shrink-0">
      <div className="flex items-center justify-between p-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <h3 className="font-bold text-sm">Thread</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md text-slate-500 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 px-3 py-4">
        {/* Parent Message Context */}
        <ChatMessage
          message={parentMessage.message}
          username={parentMessage.username}
          isOwn={parentMessage.user_id === user?.id}
          timestamp={parentMessage.timestamp || parentMessage.created_at}
        />

        <div className="flex items-center gap-2 py-2">
          <div className="h-px bg-slate-200 dark:bg-slate-800 flex-1" />
          <span className="text-[10px] font-bold text-muted uppercase tracking-wider">
            Replies
          </span>
          <div className="h-px bg-slate-200 dark:bg-slate-800 flex-1" />
        </div>

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

      <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <ChatInput onSendMessage={handleSendMessage} disabled={!isConnected} />
      </div>
    </div>
  );
}
