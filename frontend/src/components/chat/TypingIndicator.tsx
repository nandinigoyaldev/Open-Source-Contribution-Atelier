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
        "flex flex-col gap-1 px-1 py-1 text-xs font-bold text-muted",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-end">
        <div className="flex -space-x-1.5 mr-2">
          {users.slice(0, 3).map((u, i) => (
            <img
              key={u.user_id}
              src={`https://github.com/${u.username}.png`}
              alt={u.username}
              className="w-6 h-6 rounded-full border-2 border-white dark:border-[#151411] z-10 transition-transform duration-300"
              style={{ zIndex: 10 - i }}
            />
          ))}
        </div>
        <div className="bg-[#e4e4e7] dark:bg-[#2d1a28] rounded-2xl rounded-bl-sm px-3 py-2 border border-outline dark:border-[#4d2a48] shadow-sm flex items-center h-8">
          <span className="flex gap-1">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-pink-500" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-pink-500 [animation-delay:0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-pink-500 [animation-delay:0.3s]" />
          </span>
        </div>
      </div>
      <span className="text-[10px] pl-1 opacity-70 animate-pulse">{label}</span>
    </div>
  );
}
