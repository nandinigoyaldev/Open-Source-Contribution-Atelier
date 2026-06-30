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
    <div className="flex items-end gap-2 border-t border-outline bg-surface-low px-4 py-3">
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
        className="min-h-[40px] w-full resize-none rounded-xl border border-outline bg-surface-high px-3 py-2 text-sm text-text placeholder-muted outline-none focus:border-accent disabled:opacity-50"
      />
      <span className={`text-right text-xs ${text.length >= 1800 ? "text-red-500" : "text-muted"}`}>
  {text.length}/2000
     </span>
      </div>
      <button
        onClick={handleSend}
        disabled={!text.trim() || disabled}
        className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-black transition-opacity hover:opacity-80 disabled:opacity-40"
        aria-label="Send message"
      >
        <Send size={16} />
      </button>
    </div>
  );
}
