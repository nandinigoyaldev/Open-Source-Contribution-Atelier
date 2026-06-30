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
          "max-w-[75%] rounded-2xl px-4 py-2",
          isOwn
            ? "bg-accent text-black rounded-br-md"
            : "bg-surface-high text-text rounded-bl-md border border-outline",
        )}
      >
        {!isOwn && (
          <p className="text-[11px] font-bold text-muted mb-0.5">{username}</p>
        )}
        <p className="text-sm leading-snug">{message}</p>
        {timestamp && (
          <p
            className={clsx(
              "text-[10px] mt-1 text-right",
              isOwn ? "text-black/60" : "text-muted",
            )}
          >
            {timestamp}
          </p>
        )}
      </div>
    </div>
  );
}
