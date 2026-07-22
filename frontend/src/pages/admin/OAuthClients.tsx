import React, { useState, useEffect } from "react";
import {
  Shield,
  Plus,
  Key,
  Copy,
  Trash2,
  Check,
  ExternalLink,
} from "lucide-react";
import api from "../../api";

interface OAuthClientData {
  id: number;
  name: string;
  clientId: string;
  clientSecret?: string;
  clientType: "confidential" | "public";
  redirectUris: string[];
  allowedScopes: string[];
  isActive: boolean;
  createdAt: string;
}

export function OAuthClients() {
  const [clients, setClients] = useState<OAuthClientData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [clientType, setClientType] = useState<"confidential" | "public">(
    "confidential",
  );
  const [redirectUrisInput, setRedirectUrisInput] = useState(
    "http://localhost:3000/callback",
  );
  const [scopesInput, setScopesInput] = useState(
    "openid profile email lesson:read",
  );

  const fetchClients = async () => {
    try {
      setIsLoading(true);
      const res = await api.get<OAuthClientData[]>("/oauth/clients/");
      setClients(res.data || []);
    } catch (err) {
      console.error("Failed to fetch OAuth clients:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  const handleCreateClient = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const redirectUris = redirectUrisInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const allowedScopes = scopesInput
        .split(" ")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await api.post<OAuthClientData>("/oauth/clients/", {
        name,
        clientType,
        redirectUris,
        allowedScopes,
      });

      setShowCreateModal(false);
      setName("");
      fetchClients();

      if (res.data?.clientSecret) {
        alert(
          `Client Created Successfully!\n\nClient ID: ${res.data.clientId}\nClient Secret: ${res.data.clientSecret}\n\nSave your Client Secret now. It will not be shown again!`,
        );
      }
    } catch (err) {
      console.error("Failed to create OAuth client:", err);
      alert("Failed to create OAuth client");
    }
  };

  const handleDeleteClient = async (id: number) => {
    if (
      !confirm("Are you sure you want to delete this OAuth client application?")
    )
      return;
    try {
      await api.delete(`/oauth/clients/${id}/`);
      fetchClients();
    } catch (err) {
      console.error("Failed to delete client:", err);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(label);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="w-full min-h-screen flex flex-col gap-6 p-4 md:p-8 bg-surface dark:bg-[#0a0a0f] text-text dark:text-[#f0ebe2]">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b-2 border-black/10 dark:border-[#2e2924]">
        <div>
          <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            <Shield className="w-8 h-8 text-accent" /> OAuth 2.0 Client
            Applications
          </h1>
          <p className="text-sm font-medium text-muted dark:text-[#c4bbae]">
            Manage OAuth 2.0 & OpenID Connect applications, redirect URIs, and
            scopes.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 text-xs font-black px-4 py-2 bg-accent text-white rounded-xl hover:bg-accent/90 transition-all shadow-card-sm"
        >
          <Plus className="w-4 h-4" /> Register New Application
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted dark:text-[#a0988c]">
          Loading registered OAuth clients...
        </div>
      ) : clients.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl flex flex-col items-center gap-3">
          <Key className="w-12 h-12 text-muted/40" />
          <h3 className="text-lg font-bold text-text dark:text-[#f0ebe2]">
            No Applications Registered
          </h3>
          <p className="text-xs text-muted dark:text-[#a0988c]">
            Register a third-party or mobile application to issue Client ID and
            Secret credentials.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {clients.map((client) => (
            <div
              key={client.id}
              className="p-6 bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl flex flex-col justify-between gap-4 shadow-sm"
            >
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-black text-text dark:text-[#f0ebe2]">
                    {client.name}
                  </h3>
                  <span
                    className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${
                      client.clientType === "confidential"
                        ? "bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950/40 dark:text-purple-300"
                        : "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950/40 dark:text-blue-300"
                    }`}
                  >
                    {client.clientType}
                  </span>
                </div>

                <div className="flex flex-col gap-1 text-xs font-mono">
                  <div className="text-muted dark:text-[#a0988c] font-sans font-bold uppercase text-[10px]">
                    Client ID
                  </div>
                  <div className="flex items-center justify-between bg-surface-low dark:bg-[#1f1c18] p-2 rounded border border-black/10 dark:border-[#2e2924]">
                    <span className="truncate">{client.clientId}</span>
                    <button
                      onClick={() =>
                        copyToClipboard(client.clientId, `id-${client.id}`)
                      }
                      className="p-1 text-muted hover:text-accent"
                    >
                      {copiedKey === `id-${client.id}` ? (
                        <Check className="w-3.5 h-3.5 text-green-500" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <div className="text-muted dark:text-[#a0988c] font-sans font-bold uppercase text-[10px]">
                    Redirect URIs
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {client.redirectUris?.map((uri, idx) => (
                      <span
                        key={idx}
                        className="text-xs font-mono px-2 py-1 bg-surface-low dark:bg-[#1a1714] border border-black/10 dark:border-[#2e2924] rounded flex items-center gap-1"
                      >
                        <ExternalLink className="w-3 h-3 text-muted" /> {uri}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <div className="text-muted dark:text-[#a0988c] font-sans font-bold uppercase text-[10px]">
                    Allowed Scopes
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {client.allowedScopes?.map((scope, idx) => (
                      <span
                        key={idx}
                        className="text-[11px] font-mono px-2 py-0.5 bg-accent/10 text-accent rounded font-bold"
                      >
                        {scope}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-black/10 dark:border-[#2e2924] flex justify-end">
                <button
                  onClick={() => handleDeleteClient(client.id)}
                  className="flex items-center gap-1 text-xs font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" /> Delete Client
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal for Client Registration */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[#151411] border-2 border-black/20 dark:border-[#2e2924] rounded-2xl max-w-lg w-full p-6 flex flex-col gap-4 shadow-xl">
            <h2 className="text-xl font-black text-text dark:text-[#f0ebe2]">
              Register OAuth Application
            </h2>

            <form onSubmit={handleCreateClient} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold uppercase text-muted">
                  Application Name
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Mobile iOS App"
                  className="px-3 py-2 bg-surface-low dark:bg-[#1a1714] border border-black/20 dark:border-[#2e2924] rounded-lg text-sm text-text dark:text-[#f0ebe2]"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold uppercase text-muted">
                  Client Type
                </label>
                <select
                  value={clientType}
                  onChange={(e) => setClientType(e.target.value as any)}
                  className="px-3 py-2 bg-surface-low dark:bg-[#1a1714] border border-black/20 dark:border-[#2e2924] rounded-lg text-sm font-bold text-text dark:text-[#f0ebe2]"
                >
                  <option value="confidential">
                    Confidential (Server App with Secret)
                  </option>
                  <option value="public">
                    Public (SPA or Native Mobile App)
                  </option>
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold uppercase text-muted">
                  Redirect URIs (comma separated)
                </label>
                <input
                  type="text"
                  required
                  value={redirectUrisInput}
                  onChange={(e) => setRedirectUrisInput(e.target.value)}
                  className="px-3 py-2 bg-surface-low dark:bg-[#1a1714] border border-black/20 dark:border-[#2e2924] rounded-lg text-sm font-mono text-text dark:text-[#f0ebe2]"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold uppercase text-muted">
                  Allowed Scopes (space separated)
                </label>
                <input
                  type="text"
                  value={scopesInput}
                  onChange={(e) => setScopesInput(e.target.value)}
                  className="px-3 py-2 bg-surface-low dark:bg-[#1a1714] border border-black/20 dark:border-[#2e2924] rounded-lg text-sm font-mono text-text dark:text-[#f0ebe2]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-xs font-bold text-muted hover:bg-black/5 dark:hover:bg-white/5 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-black bg-accent text-white rounded-lg hover:bg-accent/90"
                >
                  Create Application
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
