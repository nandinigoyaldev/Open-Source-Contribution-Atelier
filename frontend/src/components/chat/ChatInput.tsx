import { useState, useCallback, KeyboardEvent } from "react";
import { Send } from "lucide-react";

type ChatInputProps = {
  onSendMessage: (message: string) => void | Promise<void>;
  onInputChange?: () => void;
  onInputBlur?: () => void;
  onInputSubmit?: () => void;
  placeholder?: string;
  disabled?: boolean;
};

export function ChatInput({
  onSendMessage,
  onInputChange,
  onInputBlur,
  onInputSubmit,
  placeholder = "Type a message...",
  disabled = false,
}: ChatInputProps) {
  const [text, setText] = useState("");

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;

    try {
      const result = onSendMessage(trimmed);
      if (result instanceof Promise) {
        result.catch((err) => console.error("Failed to send message:", err));
      }
    } catch (err) {
      console.error("Failed to send message:", err);
    }

    setText("");
    onInputSubmit?.();
  }, [text, disabled, onSendMessage, onInputSubmit]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setText(e.target.value);
      onInputChange?.();
    },
    [onInputChange],
  );

  return (
    <div className="flex items-end gap-2 border-t border-outline bg-[#f5f4f0] px-4 py-3 dark:border-[#3a3a45] dark:bg-[#121218]">
      <div className="flex flex-1 flex-col gap-1">
        <textarea
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={onInputBlur}
          placeholder={placeholder}
          disabled={disabled}
          maxLength={2000}
          rows={1}
          className="min-h-[40px] w-full resize-none rounded-xl border border-outline bg-white px-3 py-2 text-sm text-text placeholder-muted outline-none focus:border-[#a3a3ad] disabled:opacity-50 dark:border-[#3a3a45] dark:bg-[#1a1a24] dark:text-[#eef2f6] dark:placeholder:text-[#64748b]/75 dark:focus:border-[#5a5a6a]"
        />
        <span
          className={`text-right text-xs ${text.length >= 1800 ? "text-red-500" : "text-muted dark:text-[#64748b]"}`}
        >
          {text.length}/2000
        </span>
      </div>
      <button
        onClick={handleSend}
        disabled={!text.trim() || disabled}
        className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#d4d4d4] text-black transition-opacity hover:opacity-80 disabled:opacity-40 dark:bg-[#2a2a35] dark:text-[#94a3b8] dark:hover:bg-[#3a3a45]"
        aria-label="Send message"
      >
        <Send size={16} />
      </button>
    </div>
  );
}
