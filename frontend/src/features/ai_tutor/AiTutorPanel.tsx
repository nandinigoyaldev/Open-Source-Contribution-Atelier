// frontend/src/features/ai_tutor/AiTutorPanel.tsx

import React, { useState } from "react";
// ... existing imports

export function AITutorFloatingPanel({ lessonSlug, lessonTitle }: { lessonSlug: string; lessonTitle: string }) {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }, { role: "assistant", content: "" }]);
    setIsStreaming(true);

    try {
      const response = await fetch("/api/ai_tutor/ask/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // Include auth headers/csrf token as required by your app
        },
        body: JSON.stringify({ prompt: userMessage, lesson_slug: lessonSlug }),
      });

      if (!response.ok || !response.body) {
        throw new Error("Failed to connect to AI Tutor stream");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;
      let accumulatedResponse = "";

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunkStr = decoder.decode(value, { stream: true });
          const lines = chunkStr.split("\n\n");
          
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataText = line.replace("data: ", "").trim();
              if (dataText === "[DONE]") {
                done = true;
                break;
              }
              try {
                const parsed = JSON.parse(dataText);
                if (parsed.chunk) {
                  accumulatedResponse += parsed.chunk;
                  setMessages((prev) => {
                    const newMsgs = [...prev];
                    newMsgs[newMsgs.length - 1].content = accumulatedResponse;
                    return newMsgs;
                  });
                }
              } catch {
                // Ignore parsing errors on partial chunks
              }
            }
          }
        }
      }
    } catch (err) {
      console.error("Stream error:", err);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div>
      {/* Component UI markup for chat messages, input field, etc. */}
    </div>
  );
}
