import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { useChat } from "../hooks/useChat";
import { ChatMessage } from "../components/chat/ChatMessage";
import { ChatInput } from "../components/chat/ChatInput";
import { TypingIndicator } from "../components/chat/TypingIndicator";
import { getAccessToken } from "../lib/authToken";
import { Radio, Hash } from "lucide-react";
import { ResponsiveSidebar } from "../components/layout/ResponsiveSidebar";

import { ConnectionStatusIndicator } from "../components/ui/ConnectionStatusIndicator";

function getAvatarColor(name: string): string {
  const colors = [
    "bg-red-500",
    "bg-blue-500",
    "bg-green-500",
    "bg-yellow-500",
    "bg-purple-500",
    "bg-pink-500",
    "bg-indigo-500",
    "bg-teal-500",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

function getInitials(name: string): string {
  return name.charAt(0).toUpperCase();
}

export function ChatPage() {
  const { user } = useAuth();
  const token = getAccessToken();
  const navigate = useNavigate();
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { roomId: paramRoomId } = useParams<{ roomId?: string }>();
  const roomId = paramRoomId || "general";

  const { data: rooms = [] } = useQuery({
    queryKey: ["chatRooms"],
    queryFn: () => fetchApi("/chat/rooms/"),
  });

  interface ChatRoom {
    room_id: string;
    dm_user?: string;
  }
  const dmRooms = (rooms as ChatRoom[]).filter((r) =>
    r.room_id.startsWith("dm_"),
  );

  const {
    messages,
    typingUsers,
    onlineUsers,
    isConnected,
    state,
    getMetrics,
    sendMessage,
    onInputChange,
    onInputBlur,
    onInputSubmit,
  } = useChat({ roomId, token, username: user?.username });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUsers]);

  const renderSidebarContent = () => (
    <div className="flex flex-col h-full min-h-0 select-none">
      {/* Active channels */}
      <div className="p-3">
        <span className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest px-2">
          Rooms
        </span>
        <div className="mt-1.5 space-y-1">
          <Link
            to="/chat/general"
            onClick={() => setShowMobileSidebar(false)}
            className={`w-full flex items-center gap-2 px-3 py-2 ${roomId === "general" ? "bg-[#C3C0FF]/15 text-[#8884d8]" : "text-slate-600 dark:text-slate-400 hover:bg-black/5 dark:hover:bg-white/5"} font-bold text-xs rounded-xl transition-all`}
          >
            <Hash size={14} /> general
          </Link>
        </div>
      </div>

      {dmRooms.length > 0 && (
        <div className="p-3 pt-0">
          <span className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest px-2">
            Direct Messages
          </span>
          <div className="mt-1.5 space-y-1">
            {dmRooms.map((room) => (
              <Link
                key={room.room_id}
                to={`/chat/${room.room_id}`}
                onClick={() => setShowMobileSidebar(false)}
                className={`w-full flex items-center gap-2 px-3 py-2 ${roomId === room.room_id ? "bg-[#C3C0FF]/15 text-[#8884d8]" : "text-slate-600 dark:text-slate-400 hover:bg-black/5 dark:hover:bg-white/5"} font-bold text-xs rounded-xl transition-all`}
              >
                <div
                  className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] uppercase ${getAvatarColor(room.dm_user || "?")}`}
                >
                  {getInitials(room.dm_user || "?")}
                </div>
                {room.dm_user || "Unknown"}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Online Members List */}
      <div className="flex-grow flex flex-col min-h-0 p-3 pt-1 border-t border-black/5 dark:border-white/5 mt-2 overflow-hidden">
        <span className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest px-2 mb-2">
          Online ({onlineUsers.length})
        </span>
        <div className="flex-grow overflow-y-auto custom-scrollbar space-y-2 pr-1">
          {onlineUsers.map((member) => (
            <div
              key={member.user_id}
              onClick={() => {
                setShowMobileSidebar(false);
                if (!user || user.id === member.user_id) return;
                const min = Math.min(user.id, member.user_id);
                const max = Math.max(user.id, member.user_id);
                navigate(`/chat/dm_${min}_${max}`);
              }}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors ${user?.id !== member.user_id ? "hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer" : "opacity-75"}`}
            >
              {/* Status avatar */}
              <div className="relative">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center font-black text-[9px] uppercase border border-black/5 ${getAvatarColor(member.username)}`}
                >
                  {getInitials(member.username)}
                </div>
                <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 bg-green-500 border border-white dark:border-slate-900 rounded-full" />
              </div>
              <span className="text-xs font-bold text-slate-700 dark:text-[#a0a0ab] truncate">
                @{member.username} {user?.id === member.user_id && "(You)"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="w-full max-w-6xl mx-auto h-[calc(100vh-172px)] md:h-[calc(100vh-12rem)] flex flex-col justify-center min-h-0 overflow-hidden px-0 md:px-4">
      <div className="rounded-none md:rounded-[24px] border-0 md:border border-black/10 bg-white/80 shadow-none md:shadow-md backdrop-blur-xl dark:bg-[#15141b]/80 dark:border-white/10 flex flex-row h-full min-h-0 overflow-hidden">
        {/* Left Side: Channel / Workspace Info & Online Members (Desktop) */}
        <aside className="w-[240px] border-r border-black/10 dark:border-white/10 hidden md:flex flex-col bg-slate-50/50 dark:bg-black/10 h-full min-h-0 select-none">
          {/* Header */}
          <div className="p-4 border-b border-black/5 dark:border-white/5">
            <h3 className="font-black text-sm uppercase tracking-wider text-slate-800 dark:text-white flex items-center gap-2">
              <Radio size={14} className="text-[#8884d8]" /> Workspace Chat
            </h3>
          </div>
          {renderSidebarContent()}
        </aside>

        {/* Mobile Swipeable Channels Drawer */}
        <ResponsiveSidebar
          isOpen={showMobileSidebar}
          onClose={() => setShowMobileSidebar(false)}
          title={
            <span className="flex items-center gap-2">
              <Radio size={14} className="text-[#8884d8]" /> Workspace Chat
            </span>
          }
        >
          {renderSidebarContent()}
        </ResponsiveSidebar>

        {/* Right Side: Active Chat Message Area */}
        <section className="flex-1 flex flex-col h-full min-h-0 bg-transparent p-4 md:p-5">
          {/* Channel Header */}
          <div className="flex items-center justify-between pb-3 border-b border-black/10 dark:border-white/10 mb-4 flex-shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <button
                onClick={() => setShowMobileSidebar(true)}
                className="md:hidden p-1.5 border-2 border-black rounded-lg bg-surface-low dark:border-[#2e2924] dark:text-[#f0ebe2] mr-1 flex items-center justify-center touch-target-min"
                aria-label="Toggle Channels"
              >
                <Radio size={16} />
              </button>
              {roomId.startsWith("dm_") ? (
                <div className="w-5 h-5 rounded-full flex items-center justify-center font-black text-[8px] bg-indigo-500 text-white uppercase flex-shrink-0">
                  DM
                </div>
              ) : (
                <Hash
                  size={18}
                  className="text-slate-400 dark:text-slate-500 flex-shrink-0"
                />
              )}
              <h2 className="text-base md:text-lg font-black text-slate-800 dark:text-white truncate">
                {roomId.startsWith("dm_") ? "Direct Message" : roomId}
              </h2>
            </div>
            <ConnectionStatusIndicator state={state} getMetrics={getMetrics} />
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto min-h-0 space-y-3 px-1 mb-3 custom-scrollbar">
            {messages.length === 0 && (
              <p className="text-center text-xs text-slate-400 py-12">
                No messages in{" "}
                {roomId.startsWith("dm_") ? "this DM" : `#${roomId}`} yet. Say
                hello! 👋
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
          <TypingIndicator
            users={typingUsers}
            className="px-1 pb-1 flex-shrink-0"
          />

          <ChatInput
            onSendMessage={sendMessage}
            onInputChange={onInputChange}
            onInputBlur={onInputBlur}
            onInputSubmit={onInputSubmit}
            disabled={!isConnected}
          />
        </section>
      </div>
    </div>
  );
}
