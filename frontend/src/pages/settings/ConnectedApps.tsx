import React, { useState, useEffect } from "react";
import { Shield, Key, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import api from "../../api";

interface UserAppToken {
  id: number;
  clientId: string;
  clientName: string;
  scope: string;
  accessTokenExpiresAt: string;
  createdAt: string;
  isRevoked: boolean;
}

export function ConnectedApps() {
  const [tokens, setTokens] = useState<UserAppToken[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUserApps = async () => {
    try {
      setIsLoading(true);
      const res = await api.get<UserAppToken[]>("/oauth/user-apps/");
      setTokens(res.data || []);
    } catch (err) {
      console.error("Failed to fetch connected apps:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUserApps();
  }, []);

  const handleRevoke = async (id: number) => {
    if (
      !confirm("Are you sure you want to revoke access for this application?")
    )
      return;
    try {
      await api.post(`/oauth/user-apps/${id}/revoke/`);
      fetchUserApps();
    } catch (err) {
      console.error("Failed to revoke application access:", err);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6 p-4 md:p-8 bg-surface dark:bg-[#0a0a0f] text-text dark:text-[#f0ebe2]">
      <div className="pb-4 border-b-2 border-black/10 dark:border-[#2e2924]">
        <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
          <Shield className="w-8 h-8 text-accent" /> Connected Applications
        </h1>
        <p className="text-sm font-medium text-muted dark:text-[#c4bbae]">
          Third-party apps and integrations authorized to access your account
          data.
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted dark:text-[#a0988c]">
          Loading authorized applications...
        </div>
      ) : tokens.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-2xl flex flex-col items-center gap-3 shadow-sm">
          <Key className="w-12 h-12 text-muted/40" />
          <h3 className="text-lg font-bold text-text dark:text-[#f0ebe2]">
            No Active Applications
          </h3>
          <p className="text-xs text-muted dark:text-[#a0988c] max-w-sm">
            You haven't granted third-party applications access to your account.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {tokens.map((token) => (
            <div
              key={token.id}
              className="p-5 bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl flex items-center justify-between gap-4 shadow-sm flex-wrap"
            >
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-black text-text dark:text-[#f0ebe2]">
                    {token.clientName}
                  </h3>
                  <span className="text-xs font-mono text-muted">
                    ({token.clientId})
                  </span>
                </div>

                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <span className="font-bold text-muted dark:text-[#a0988c]">
                    Granted Permissions:
                  </span>
                  {token.scope.split(" ").map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 font-mono text-[11px] rounded font-bold"
                    >
                      {s}
                    </span>
                  ))}
                </div>

                <div className="text-[11px] text-muted dark:text-[#a0988c]">
                  Authorized on {new Date(token.createdAt).toLocaleDateString()}
                </div>
              </div>

              <button
                onClick={() => handleRevoke(token.id)}
                className="flex items-center gap-1.5 text-xs font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 px-3 py-2 rounded-xl transition-colors border border-red-200 dark:border-red-900/50"
              >
                <Trash2 className="w-4 h-4" /> Revoke Access
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
