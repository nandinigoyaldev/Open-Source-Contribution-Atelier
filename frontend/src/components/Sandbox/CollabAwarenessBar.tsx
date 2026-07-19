import React from "react";
import { CollabUser } from "../../hooks/useYjsProvider";

interface CollabAwarenessBarProps {
  connected: boolean;
  collaborators: CollabUser[];
  sessionId: string;
}

export function CollabAwarenessBar({
  connected,
  collaborators,
  sessionId,
}: CollabAwarenessBarProps) {
  const inviteLink = `${window.location.origin}/collab/${sessionId}`;

  const copyLink = () => {
    navigator.clipboard.writeText(inviteLink).catch(() => {});
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm">
      {/* Connection status */}
      <span className="flex items-center gap-1.5">
        <span
          className={`h-2 w-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`}
          aria-label={connected ? "Connected" : "Disconnected"}
        />
        <span className="text-white/60">
          {connected ? "Live" : "Reconnecting…"}
        </span>
      </span>

      <span className="text-white/20">|</span>

      {/* Online collaborators */}
      <div
        className="flex items-center gap-2"
        aria-label="Online collaborators"
      >
        {collaborators.length === 0 ? (
          <span className="text-white/40 italic">Only you here</span>
        ) : (
          collaborators.map((user) => (
            <span
              key={user.clientId}
              title={`${user.name}${user.activeFileId ? ` – editing ${user.activeFileId}` : ""}`}
              className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold text-white"
              style={{ backgroundColor: user.color }}
            >
              {user.name.charAt(0).toUpperCase()}
            </span>
          ))
        )}
      </div>

      {/* Invite link */}
      <button
        id="collab-copy-invite-btn"
        onClick={copyLink}
        className="ml-auto rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-indigo-500 active:scale-95"
        aria-label="Copy invite link"
      >
        Copy Invite Link
      </button>
    </div>
  );
}
