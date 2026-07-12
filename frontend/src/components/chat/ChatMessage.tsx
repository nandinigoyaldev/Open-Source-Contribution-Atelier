import clsx from "clsx";

type ChatMessageProps = {
  message: string;
  username: string;
  isOwn: boolean;
  timestamp?: string;
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
    <div className={clsx("flex gap-2.5 items-end mb-2.5", isOwn ? "flex-row-reverse" : "flex-row")}>
      <div className="flex-shrink-0">
        <div
          className={clsx(
            "w-8 h-8 rounded-full flex items-center justify-center font-black text-xs border border-black/5 shadow-sm uppercase select-none",
            getAvatarColor(username)
          )}
        >
          {getInitials(username)}
        </div>
      </div>

      <div className="flex flex-col max-w-[70%]">
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
              : "bg-slate-50 text-gray-900 border-black/5 rounded-bl-none dark:bg-slate-800/80 dark:text-gray-100 dark:border-slate-700/60"
          )}
        >
          <p className="whitespace-pre-wrap break-words">{message}</p>
        </div>
        {timestamp && (
          <span
            className={clsx(
              "text-[9px] text-muted/65 dark:text-gray-400 mt-1",
              isOwn ? "text-right mr-1" : "text-left ml-1"
            )}
          >
            {timestamp}
          </span>
        )}
      </div>
    </div>
  );
}
