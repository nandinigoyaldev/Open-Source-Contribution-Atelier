import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchApi } from "../../lib/api";
import {
  Sparkles,
  Send,
  X,
  Bot,
  Loader2,
  MessageSquare,
  RotateCcw,
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const QUICK_PROMPTS = [
  "What is Git?",
  "What is a commit?",
  "How do PRs work?",
  "Tell me about open source licenses",
];

export function AITutorFloatingPanel({
  lessonSlug,
  lessonTitle,
}: {
  lessonSlug?: string;
  lessonTitle?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const tutorMutation = useMutation({
    mutationFn: (question: string) => {
      const historyPairs: { question: string; answer: string }[] = [];
      for (let i = 0; i < messages.length - 1; i++) {
        if (
          messages[i].role === "user" &&
          messages[i + 1]?.role === "assistant"
        ) {
          historyPairs.push({
            question: messages[i].content,
            answer: messages[i + 1].content,
          });
        }
      }

      return fetchApi<{ answer: string }>("/ai/tutor/ask/", {
        method: "POST",
        body: JSON.stringify({
          question,
          lesson_slug: lessonSlug,
          history: historyPairs,
        }),
        headers: { "Content-Type": "application/json" },
      });
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, I couldn't process that right now. Please try again.",
        },
      ]);
    },
  });

  const sendQuestion = (qText: string) => {
    const q = qText.trim();
    if (!q || tutorMutation.isPending) return;
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setInput("");
    tutorMutation.mutate(q);
  };

  const handleSend = () => {
    sendQuestion(input);
  };

  const handleReset = () => {
    setMessages([
      {
        role: "assistant",
        content: lessonTitle
          ? `Hi! I'm your AI tutor for **${lessonTitle}**. Ask me anything about this lesson or open source in general!`
          : "Hi! I'm your AI tutor. Ask me anything about open source contribution!",
      },
    ]);
  };

  return (
    <>
      {!isOpen && (
        <button
          onClick={() => {
            setIsOpen(true);
            if (messages.length === 0) {
              handleReset();
            }
          }}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-accent border-4 border-black rounded-full shadow-card hover:-translate-y-1 transition-all flex items-center justify-center"
          aria-label="Open AI Tutor"
        >
          <Bot className="w-7 h-7 text-white" />
        </button>
      )}

      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-80 sm:w-96 h-[520px] bg-white border-4 border-black rounded-3xl shadow-card flex flex-col overflow-hidden dark:bg-[#151411] dark:border-[#2e2924]">
          <div className="flex items-center justify-between px-4 py-3 border-b-4 border-black dark:border-[#2e2924] bg-accent/5">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent" />
              <span className="font-black text-xs uppercase tracking-wider">
                AI Tutor
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={handleReset}
                title="Reset conversation"
                className="p-1 hover:bg-black/5 rounded-lg transition-colors dark:hover:bg-white/5 text-muted hover:text-text"
                aria-label="Reset conversation"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-black/5 rounded-lg transition-colors dark:hover:bg-white/5"
                aria-label="Close AI Tutor"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-accent text-white border-2 border-black"
                      : "bg-surface-low border-2 border-black/10 dark:border-[#2e2924] text-text dark:text-[#f0ebe2]"
                  }`}
                >
                  {msg.role === "user" ? (
                    <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  ) : (
                    <div className="text-[13px] leading-relaxed prose dark:prose-invert max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p({ children }) {
                            return (
                              <p className="mb-1.5 last:mb-0">{children}</p>
                            );
                          },
                          code({ children }) {
                            return (
                              <code className="bg-black/10 dark:bg-white/10 px-1 py-0.5 rounded text-[12px] font-mono">
                                {children}
                              </code>
                            );
                          },
                          ul({ children }) {
                            return (
                              <ul className="list-disc pl-4 mb-1.5 space-y-0.5">
                                {children}
                              </ul>
                            );
                          },
                          ol({ children }) {
                            return (
                              <ol className="list-decimal pl-4 mb-1.5 space-y-0.5">
                                {children}
                              </ol>
                            );
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {messages.length <= 1 && (
              <div className="pt-2">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted mb-2">
                  Suggested Questions:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {QUICK_PROMPTS.map((promptText) => (
                    <button
                      key={promptText}
                      onClick={() => sendQuestion(promptText)}
                      disabled={tutorMutation.isPending}
                      className="text-left text-xs bg-surface-low border border-black/20 hover:border-accent hover:bg-accent/10 px-2.5 py-1 rounded-xl transition-all dark:bg-[#1a1815] dark:border-[#2e2924] dark:text-[#c4bbae]"
                    >
                      {promptText}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {tutorMutation.isPending && (
              <div className="flex justify-start">
                <div className="bg-surface-low border-2 border-black/10 dark:border-[#2e2924] rounded-2xl px-4 py-3 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-accent" />
                  <span className="text-xs text-muted dark:text-[#c4bbae]">
                    Thinking...
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="border-t-4 border-black dark:border-[#2e2924] p-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Ask a question..."
                className="flex-1 px-3 py-2 text-sm border-2 border-black/20 rounded-xl bg-surface-low focus:outline-none focus:border-accent dark:bg-[#0f0e0c] dark:border-[#2e2924] dark:text-[#f0ebe2] dark:focus:border-accent"
                disabled={tutorMutation.isPending}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || tutorMutation.isPending}
                className="p-2 bg-accent text-white border-2 border-black rounded-xl hover:bg-accent/90 disabled:opacity-50 transition-colors"
                aria-label="Send question"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-[9px] text-muted mt-1.5 text-center font-mono uppercase tracking-wider">
              <MessageSquare className="w-2.5 h-2.5 inline mr-1" />
              AI responses are for learning guidance
            </p>
          </div>
        </div>
      )}
    </>
  );
}
