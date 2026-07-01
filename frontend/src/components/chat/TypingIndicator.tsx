import clsx from "clsx";

type TypingUser = {
  username: string;
  user_id: number;
};

type TypingIndicatorProps = {
  users: TypingUser[];
  className?: string;
};

export function TypingIndicator({ users, className }: TypingIndicatorProps) {
  if (users.length === 0) return null;

  const usernames = users.map((u) => u.username);
  const label =
    users.length === 1
      ? `${usernames[0]} is typing...`
      : users.length === 2
        ? `${usernames[0]} and ${usernames[1]} are typing...`
        : `${usernames[0]} and ${users.length - 1} others are typing...`;

  return (
    <div
      className={clsx(
        "flex items-center gap-2 px-1 py-1 text-xs font-bold text-muted",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <span className="flex gap-0.5">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:0.3s]" />
      </span>
      <span>{label}</span>
    </div>
  );
}
