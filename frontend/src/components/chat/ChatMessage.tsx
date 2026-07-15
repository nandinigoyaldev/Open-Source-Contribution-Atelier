import clsx from "clsx";

import { MessageSquare } from "lucide-react";

type ChatMessageProps = {
  message: string;
  username: string;
  isOwn: boolean;
  timestamp?: string;
  replyCount?: number;
  onReply?: () => void;
};

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

export function ChatMessage({
  message,
  username,
  isOwn,
  timestamp,
}: ChatMessageProps) {
  return (
    <div
      className={clsx(
        "flex gap-2.5 items-end mb-2.5",
        isOwn ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div className="flex-shrink-0">
        <div
          className={clsx(
            "w-8 h-8 rounded-full flex items-center justify-center font-black text-xs border border-black/5 shadow-sm uppercase select-none",
            getAvatarColor(username),
          )}
        >
          {getInitials(username)}
        </div>
      </div>

      <div className="flex flex-col max-w-[70%] group">
        {!isOwn && (
          <span className="text-[10px] font-black text-slate-500 dark:text-[#a0a0ab] ml-1 mb-0.5">
            @{username}
          </span>
        )}
        <div
          className={clsx(
            "rounded-2xl px-4 py-2 border text-sm leading-relaxed transition-all shadow-sm",
            isOwn
              ? "bg-[#C3C0FF] text-black border-black/10 rounded-br-none dark:bg-[#2e2640] dark:text-[#f0ebe2] dark:border-[#4d3a60]"
              : "bg-slate-50 text-gray-900 border-black/5 rounded-bl-none dark:bg-slate-800/80 dark:text-gray-100 dark:border-slate-700/60",
          )}
        >
          <p className="whitespace-pre-wrap break-words">{message}</p>

          {onReply && (
            <button
              onClick={onReply}
              className={clsx(
                "absolute -right-10 top-1/2 -translate-y-1/2 p-1.5 rounded-full bg-white dark:bg-slate-700 shadow-sm border border-black/5 opacity-0 group-hover:opacity-100 transition-opacity text-slate-500 hover:text-indigo-600",
                isOwn && "-left-10 right-auto",
              )}
              title="Reply in thread"
            >
              <MessageSquare size={14} />
            </button>
          )}
        </div>

        <div
          className={clsx(
            "flex items-center gap-2 mt-1",
            isOwn ? "justify-end mr-1" : "justify-start ml-1",
          )}
        >
          {timestamp && (
            <span className="text-[9px] text-muted/65 dark:text-gray-400">
              {timestamp}
            </span>
          )}
          {!!replyCount && replyCount > 0 && (
            <button
              onClick={onReply}
              className="text-[10px] font-bold text-indigo-600 hover:underline flex items-center gap-1"
            >
              {replyCount} {replyCount === 1 ? "reply" : "replies"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
