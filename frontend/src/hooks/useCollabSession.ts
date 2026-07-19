import { useState, useEffect, useCallback } from "react";
import {
  joinCollabSession,
  deleteCollabSession,
  CollabSession,
} from "../lib/api";

export interface ProjectFile {
  id: string;
  name: string;
  content: string;
  language: string;
}

interface UseCollabSessionResult {
  session: CollabSession | null;
  files: ProjectFile[];
  loading: boolean;
  error: string | null;
  isHost: boolean;
  endSession: () => Promise<void>;
}

interface UseCollabSessionOptions {
  sessionId: string;
  currentUserId: number | null;
}

export function useCollabSession({
  sessionId,
  currentUserId,
}: UseCollabSessionOptions): UseCollabSessionResult {
  const [session, setSession] = useState<CollabSession | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    setLoading(true);
    setError(null);

    joinCollabSession(sessionId)
      .then((s) => {
        setSession(s);
        // Provide a placeholder file tree; real file loading requires
        // a project files endpoint that varies per deployment.
        setFiles([
          {
            id: "main",
            name: "main.py",
            content: "# Start collaborating here\n",
            language: "python",
          },
        ]);
      })
      .catch((err: unknown) => {
        const msg =
          err instanceof Error ? err.message : "Failed to join session";
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [sessionId]);

  const isHost =
    !!session &&
    !!currentUserId &&
    !session.allowed_users.includes(currentUserId);

  const endSession = useCallback(async () => {
    await deleteCollabSession(sessionId);
  }, [sessionId]);

  return { session, files, loading, error, isHost, endSession };
}
