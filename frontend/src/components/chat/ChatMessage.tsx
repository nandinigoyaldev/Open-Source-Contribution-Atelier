import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Prism from "prismjs";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-python";
import "prismjs/components/prism-rust";
import "prismjs/components/prism-bash";
import "prismjs/themes/prism-tomorrow.css";

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
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            className="break-words"
            components={{
              p({ children }) {
                return <p className="mb-2 last:mb-0 whitespace-pre-wrap">{children}</p>;
              },
              a({ href, children }) {
                return (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-600 dark:text-indigo-400 hover:underline">
                    {children}
                  </a>
                );
              },
              ul({ children }) {
                return <ul className="list-disc pl-4 mb-2">{children}</ul>;
              },
              ol({ children }) {
                return <ol className="list-decimal pl-4 mb-2">{children}</ol>;
              },
              code(props) {
                const { children, className, ...rest } = props;
                const match = /language-(\w+)/.exec(className || "");
                const language = match ? match[1] : "";

                if (!match) {
                  return (
                    <code className="bg-black/10 dark:bg-white/10 px-1 py-0.5 rounded text-[13px] font-mono" {...rest}>
                      {children}
                    </code>
                  );
                }

                const grammar = Prism.languages[language];
                let highlighted = String(children).replace(/\n$/, "");
                if (grammar) {
                  try {
                    highlighted = Prism.highlight(highlighted, grammar, language);
                  } catch (e) {
                    // Ignore highlight errors
                  }
                }

                return (
                  <div className="relative group/code mt-2 mb-2">
                    <div className="absolute right-2 top-2 text-[10px] text-gray-400 select-none uppercase font-bold">
                      {language}
                    </div>
                    <pre className={`language-${language} bg-[#2d2d2d] rounded-md p-3 overflow-x-auto text-[13px]`} style={{ margin: 0 }}>
                      {grammar ? (
                        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
                      ) : (
                        <code className={className} {...rest}>
                          {children}
                        </code>
                      )}
                    </pre>
                  </div>
                );
              },
            }}
          >
            {message}
          </ReactMarkdown>

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
