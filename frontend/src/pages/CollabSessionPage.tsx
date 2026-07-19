import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { useCollabSession } from "../hooks/useCollabSession";
import { useYjsProvider } from "../hooks/useYjsProvider";
import { CollabAwarenessBar } from "../components/Sandbox/CollabAwarenessBar";
import { CollabEditor } from "../components/Sandbox/CollabEditor";
import { CollabChatSidebar } from "../components/Sandbox/CollabChatSidebar";
import { CollabReviewSidebar } from "../components/Sandbox/CollabReviewSidebar";
import { fetchReviewThreads } from "../lib/api";
import type { CodeReviewThread } from "../lib/api";
import type { ProjectFile } from "../hooks/useCollabSession";

export function CollabSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [reviewThreads, setReviewThreads] = useState<CodeReviewThread[]>([]);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);

  // Fetch initial review threads
  useEffect(() => {
    if (sessionId) {
      fetchReviewThreads(sessionId)
        .then((threads) => {
          setReviewThreads(threads);
        })
        .catch((err) => {
          console.error("Failed to load review threads", err);
        });
    }
  }, [sessionId]);

  // Handle real-time thread updates
  const handleTextMessage = (data: any) => {
    if (data.action === "thread_updated" && data.thread) {
      const updatedThread = data.thread as CodeReviewThread;
      setReviewThreads((prev) => {
        const index = prev.findIndex((t) => t.id === updatedThread.id);
        if (index !== -1) {
          return prev.map((t) =>
            t.id === updatedThread.id ? updatedThread : t,
          );
        } else {
          return [...prev, updatedThread];
        }
      });
    }
  };

  const { session, files, loading, error, isHost, endSession } =
    useCollabSession({
      sessionId: sessionId ?? "",
      currentUserId: user?.id ?? null,
    });

  const {
    ydoc,
    provider,
    connected,
    collaborators,
    setActiveFile,
    sendTextMessage,
  } = useYjsProvider({
    sessionId: sessionId ?? "",
    username: user?.username ?? "Anonymous",
    onTextMessage: handleTextMessage,
  });

  const [activeFile, setActiveFileState] = useState<ProjectFile | null>(null);
  const [showChat, setShowChat] = useState(true);

  const selectFile = (file: ProjectFile) => {
    setActiveFileState(file);
    setActiveFile(file.id);
    setSelectedLine(null); // Reset selected line on file change
  };

  const handleEndSession = async () => {
    await endSession();
    navigate("/contributor-sandbox");
  };

  const handleAddComment = (
    line: number,
    content: string,
    threadId?: string,
  ) => {
    sendTextMessage({
      action: "add_comment",
      thread_id: threadId || null,
      line_number: line,
      content,
    });
  };

  const handleResolveThread = (threadId: string) => {
    sendTextMessage({
      action: "resolve_thread",
      thread_id: threadId,
    });
  };

  if (!sessionId) {
    return (
      <div className="flex h-screen items-center justify-center text-white">
        Invalid session URL.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-white/60">
        Joining session…
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 text-white">
        <p className="text-red-400">
          {error ?? "Session not found or has ended."}
        </p>
        <button
          onClick={() => navigate("/contributor-sandbox")}
          className="rounded bg-indigo-600 px-4 py-2 text-sm hover:bg-indigo-500"
        >
          Back to Sandbox
        </button>
      </div>
    );
  }

  const currentFile = activeFile ?? files[0] ?? null;

  return (
    <div className="flex h-screen flex-col gap-2 bg-[#0d0d14] p-3 text-white">
      {/* Top bar */}
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-white/70">
          Pair Programming
        </h1>
        <div className="flex-1">
          <CollabAwarenessBar
            connected={connected}
            collaborators={collaborators}
            sessionId={sessionId}
          />
        </div>
        {isHost && (
          <button
            id="collab-end-session-btn"
            onClick={handleEndSession}
            className="rounded border border-red-500/40 bg-red-500/10 px-3 py-1 text-xs font-medium text-red-400 transition hover:bg-red-500/20"
            aria-label="End collaboration session"
          >
            End Session
          </button>
        )}
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden gap-2">
        {/* File tree */}
        <aside className="flex w-44 flex-col gap-1 rounded-lg border border-white/10 bg-white/5 p-2">
          <p className="px-1 text-xs font-semibold uppercase tracking-wide text-white/40">
            Files
          </p>
          {files.map((file) => (
            <button
              key={file.id}
              id={`collab-file-${file.id}`}
              onClick={() => selectFile(file)}
              className={`rounded px-2 py-1.5 text-left text-xs transition ${
                currentFile?.id === file.id
                  ? "bg-indigo-600/40 text-white"
                  : "text-white/60 hover:bg-white/10"
              }`}
            >
              {file.name}
            </button>
          ))}
        </aside>

        {/* Editor */}
        <main className="flex flex-1 overflow-hidden rounded-lg border border-white/10">
          {currentFile ? (
            <CollabEditor
              key={currentFile.id}
              fileId={currentFile.id}
              language={currentFile.language}
              ydoc={ydoc}
              provider={provider}
              onSelectLine={setSelectedLine}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center text-white/30">
              Select a file to start editing
            </div>
          )}
        </main>

        {/* Sidebar: chat/reviews toggle */}
        <aside className="flex w-80 flex-col gap-2">
          <div className="flex gap-1">
            <button
              id="collab-tab-chat"
              onClick={() => setShowChat(true)}
              className={`flex-1 rounded py-1 text-xs font-medium transition ${
                showChat
                  ? "bg-indigo-600 text-white"
                  : "bg-white/5 text-white/50 hover:bg-white/10"
              }`}
            >
              Chat
            </button>
            <button
              id="collab-tab-review"
              onClick={() => setShowChat(false)}
              className={`flex-1 rounded py-1 text-xs font-medium transition ${
                !showChat
                  ? "bg-indigo-600 text-white"
                  : "bg-white/5 text-white/50 hover:bg-white/10"
              }`}
            >
              Reviews
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
            {showChat ? (
              <CollabChatSidebar
                sessionId={sessionId}
                username={user?.username ?? "Anonymous"}
              />
            ) : (
              <CollabReviewSidebar
                sessionId={sessionId}
                username={user?.username ?? "Anonymous"}
                selectedLine={selectedLine}
                threads={reviewThreads}
                onAddComment={handleAddComment}
                onResolveThread={handleResolveThread}
              />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
