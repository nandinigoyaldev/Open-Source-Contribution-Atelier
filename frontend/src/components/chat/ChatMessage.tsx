import clsx from "clsx";

type ChatMessageProps = {
  message: string;
  username: string;
  isOwn: boolean;
  timestamp?: string;
};

export function ChatMessage({
  message,
  username,
  isOwn,
  timestamp,
}: ChatMessageProps) {
  return (
    <div className={clsx("flex", isOwn ? "justify-end" : "justify-start")}>
      <div
        className={clsx(
          "max-w-[75%] rounded-2xl px-4 py-2 border border-outline",
          isOwn
            ? "bg-[#f0eeeb] text-black rounded-br-md dark:bg-[#1a1a20] dark:text-[#eef2f6] dark:border-[#3a3a45]"
            : "bg-[#fce7f3] text-black rounded-bl-md dark:bg-[#2d1a28] dark:text-[#eef2f6] dark:border-[#4d2a48]",
        )}
      >
        {!isOwn && (
          <p className="text-[11px] font-bold text-pink-600 mb-0.5 dark:text-pink-300">{username}</p>
        )}
        <p className="text-sm leading-snug">{message}</p>
        {timestamp && (
          <p
            className={clsx(
              "text-[10px] mt-1 text-right",
              isOwn ? "text-black/50" : "text-pink-400 dark:text-pink-200/70",
            )}
          >
            {timestamp}
          </p>
        )}
      </div>
    </div>
  );
}
