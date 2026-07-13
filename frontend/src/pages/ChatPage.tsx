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

import { Hash, Radio } from "lucide-react";

function getInitials(username: string): string {
  if (!username) return "?";
  const clean = username.replace(/^@/, "");
  return clean.slice(0, 2).toUpperCase();
}

function getAvatarColor(username: string): string {
  const colors = [
    "bg-red-500 text-white",
    "bg-blue-500 text-white",
    "bg-emerald-500 text-white",
    "bg-amber-500 text-black",
    "bg-indigo-500 text-white",
    "bg-pink-500 text-white",
    "bg-purple-500 text-white",
    "bg-cyan-500 text-black",
  ];
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % colors.length;
  return colors[index];
}

export function ChatPage() {
  const { user } = useAuth();
  const token = getAccessToken();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const roomId = "general";

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
    <div className="max-w-6xl mx-auto h-[calc(100vh-12rem)] flex flex-col justify-center min-h-0 overflow-hidden">
      <div className="rounded-[24px] border border-black/10 bg-white/80 shadow-md backdrop-blur-xl dark:bg-[#15141b]/80 dark:border-white/10 flex flex-row h-full min-h-0 overflow-hidden">
        
        {/* Left Side: Channel / Workspace Info & Online Members */}
        <aside className="w-[240px] border-r border-black/10 dark:border-white/10 hidden md:flex flex-col bg-slate-50/50 dark:bg-black/10 h-full min-h-0 select-none">
          {/* Header */}
          <div className="p-4 border-b border-black/5 dark:border-white/5">
            <h3 className="font-black text-sm uppercase tracking-wider text-slate-800 dark:text-white flex items-center gap-2">
              <Radio size={14} className="text-[#8884d8]" /> Workspace Chat
            </h3>
          </div>

          {/* Active channels */}
          <div className="p-3">
            <span className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest px-2">Rooms</span>
            <div className="mt-1.5">
              <button className="w-full flex items-center gap-2 px-3 py-2 bg-[#C3C0FF]/15 text-[#8884d8] font-bold text-xs rounded-xl transition-all">
                <Hash size={14} /> general
              </button>
            </div>
          </div>

          {/* Online Members List */}
          <div className="flex-1 flex flex-col min-h-0 p-3 pt-1 border-t border-black/5 dark:border-white/5 mt-2">
            <span className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest px-2 mb-2">
              Online ({onlineUsers.length})
            </span>
            <div className="flex-grow overflow-y-auto custom-scrollbar space-y-2 pr-1">
              {onlineUsers.map((member) => (
                <div key={member.user_id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                  {/* Status avatar */}
                  <div className="relative">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center font-black text-[9px] uppercase border border-black/5 ${getAvatarColor(member.username)}`}>
                      {getInitials(member.username)}
                    </div>
                    <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 bg-green-500 border border-white dark:border-slate-900 rounded-full" />
                  </div>
                  <span className="text-xs font-bold text-slate-700 dark:text-[#a0a0ab] truncate">
                    @{member.username}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Right Side: Active Chat Message Area */}
        <section className="flex-1 flex flex-col h-full min-h-0 bg-transparent p-5">
          {/* Channel Header */}
          <div className="flex items-center justify-between pb-3 border-b border-black/10 dark:border-white/10 mb-4 flex-shrink-0">
            <div className="flex items-center gap-2">
              <Hash size={18} className="text-slate-400 dark:text-slate-500" />
              <h2 className="text-lg font-black text-slate-800 dark:text-white">general</h2>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`} />
              <span className="text-[11px] font-bold text-slate-400 dark:text-[#a0a0ab] uppercase tracking-wider">
                {isConnected ? "Connected" : "Disconnected"}
              </span>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto min-h-0 space-y-3 px-1 mb-3 custom-scrollbar">
            {messages.length === 0 && (
              <p className="text-center text-xs text-slate-400 py-12">
                No messages in #general yet. Say hello! 👋
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

          {/* Typing Indicator */}
          <TypingIndicator users={typingUsers} className="px-1 pb-1 flex-shrink-0" />

          {/* Message Input Bar */}
          <div className="flex-shrink-0">
            <ChatInput
              onSendMessage={sendMessage}
              onInputChange={onInputChange}
              onInputBlur={onInputBlur}
              onInputSubmit={onInputSubmit}
              disabled={!isConnected}
            />
          </div>
        </section>

      </div>
    </div>
  );
}

export default ChatPage;
