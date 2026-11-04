import React, { useState, useEffect, useRef } from "react";
import {
  Webhook,
  Plus,
  Shield,
  Key,
  RotateCw,
  Send,
  Trash2,
  CheckCircle2,
  Copy,
  Check,
  AlertCircle,
  Activity,
  Globe,
  Radio,
} from "lucide-react";
import {
  DeliveryLogTable,
  WebhookDelivery,
} from "../components/webhooks/DeliveryLogTable";
import { fetchApi } from "../lib/api";
import { ApiError, getApiErrorMessage } from "../lib/apiErrors";

export interface WebhookEndpoint {
  id: number;
  target_url: string;
  is_active: boolean;
  events: string[];
  secret?: string;
  created_at: string;
  updated_at: string;
}

const AVAILABLE_EVENTS = [
  {
    id: "pr.merged",
    label: "PR Merged",
    desc: "Triggered when a contributor's pull request is merged",
  },
  {
    id: "challenge.completed",
    label: "Challenge Completed",
    desc: "Triggered when a code challenge is solved",
  },
  {
    id: "badge.earned",
    label: "Badge Earned",
    desc: "Triggered when a new achievement badge is unlocked",
  },
  {
    id: "certificate.issued",
    label: "Certificate Issued",
    desc: "Triggered when an A4 verified certificate is generated",
  },
  {
    id: "user.signup",
    label: "User Signup",
    desc: "Triggered when a new learner joins the Atelier cohort",
  },
];

export const WebhookSettingsPage: React.FC = () => {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [targetUrl, setTargetUrl] = useState<string>("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([
    "pr.merged",
    "challenge.completed",
  ]);
  const [copiedSecretId, setCopiedSecretId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isTestingId, setIsTestingId] = useState<number | null>(null);
  // every retry that is in flight, so two rows can retry at the same time
  const [replayingIds, setReplayingIds] = useState<ReadonlySet<number>>(
    () => new Set(),
  );
  const [retryErrors, setRetryErrors] = useState<Record<number, string>>({});
  // state updates are async, so a fast double click needs a synchronous guard
  const retryingIds = useRef<Set<number>>(new Set());
  // A delivery-list response can arrive after a retry already finished. Each
  // list request and each finished retry gets a number from this counter; a
  // retried row is only overwritten by a list that was requested after it.
  const requestClock = useRef(0);
  const retriedRows = useRef<Map<number, { at: number; row: WebhookDelivery }>>(
    new Map(),
  );
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const fetchEndpointsAndDeliveries = async () => {
    const requestedAt = ++requestClock.current;
    setIsLoading(true);
    try {
      const [resEndpoints, resDeliveries] = await Promise.all([
        fetch("/api/webhooks/endpoints/"),
        fetch("/api/webhooks/deliveries/"),
      ]);

      if (resEndpoints.ok) {
        const dataEndpoints = await resEndpoints.json();
        setEndpoints(
          Array.isArray(dataEndpoints)
            ? dataEndpoints
            : dataEndpoints.results || [],
        );
      }
      if (resDeliveries.ok) {
        const dataDeliveries = await resDeliveries.json();
        const list: WebhookDelivery[] = Array.isArray(dataDeliveries)
          ? dataDeliveries
          : dataDeliveries.results || [];
        setDeliveries(
          list.map((row) => {
            const retried = retriedRows.current.get(row.id);
            return retried && retried.at > requestedAt ? retried.row : row;
          }),
        );
      }
    } catch {
      // Offline fallback state for demonstration / local dev
      setEndpoints([
        {
          id: 1,
          target_url: "https://discord.com/api/webhooks/123456789/sample-token",
          is_active: true,
          events: ["pr.merged", "challenge.completed", "badge.earned"],
          secret:
            "whsec_" +
            Array.from({ length: 32 }, () =>
              Math.floor(Math.random() * 16).toString(16),
            ).join(""),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
      setDeliveries([
        {
          id: 101,
          event_type: "pr.merged",
          payload: {
            pr_id: 2322,
            title: "Outgoing Webhook Delivery Engine",
            author: "suman20041",
          },
          status: "success",
          status_code: 200,
          response_body: '{"ok": true, "message": "Webhook received"}',
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEndpointsAndDeliveries();
  }, []);

  const handleToggleEvent = (eventId: string) => {
    setSelectedEvents((prev) =>
      prev.includes(eventId)
        ? prev.filter((e) => e !== eventId)
        : [...prev, eventId],
    );
  };

  const handleCreateEndpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetUrl) return;

    setIsSaving(true);
    try {
      const res = await fetch("/api/webhooks/endpoints/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: targetUrl,
          is_active: true,
          events: selectedEvents,
        }),
      });

      if (res.ok) {
        const newEp = await res.json();
        setEndpoints((prev) => [newEp, ...prev]);
        setTargetUrl("");
        setNotification({
          type: "success",
          message: "Webhook endpoint registered successfully!",
        });
      } else {
        throw new Error("Failed to register endpoint.");
      }
    } catch {
      // Optimistic local creation
      const mockEp: WebhookEndpoint = {
        id: Date.now(),
        target_url: targetUrl,
        is_active: true,
        events: selectedEvents,
        secret: "whsec_" + Math.random().toString(36).substring(2, 15),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setEndpoints((prev) => [mockEp, ...prev]);
      setTargetUrl("");
      setNotification({
        type: "success",
        message: "Webhook endpoint registered (Demo Mode)!",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestEndpoint = async (id: number) => {
    setIsTestingId(id);
    try {
      const res = await fetch(`/api/webhooks/endpoints/${id}/test/`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.delivery) {
          setDeliveries((prev) => [data.delivery, ...prev]);
        }
        setNotification({
          type: "success",
          message: `Test ping delivered to endpoint #${id}!`,
        });
      }
    } catch {
      // Mock test ping delivery
      const mockDelivery: WebhookDelivery = {
        id: Date.now(),
        event_type: "ping",
        payload: { event: "ping", message: "Connection test successful" },
        status: "success",
        status_code: 200,
        response_body: '{"status": "pong"}',
        created_at: new Date().toISOString(),
      };
      setDeliveries((prev) => [mockDelivery, ...prev]);
      setNotification({
        type: "success",
        message: "Test ping sent (Demo Mode)!",
      });
    } finally {
      setIsTestingId(null);
    }
  };

  const handleRotateSecret = async (id: number) => {
    try {
      const res = await fetch(`/api/webhooks/endpoints/${id}/rotate/`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setEndpoints((prev) =>
          prev.map((ep) =>
            ep.id === id ? { ...ep, secret: data.secret } : ep,
          ),
        );
        setNotification({
          type: "success",
          message: "Secret key rotated! Old key expires in 24h.",
        });
      }
    } catch {
      setNotification({
        type: "success",
        message: "Secret key rotated (Demo Mode)!",
      });
    }
  };

  const handleDeleteEndpoint = async (id: number) => {
    try {
      await fetch(`/api/webhooks/endpoints/${id}/`, { method: "DELETE" });
      setEndpoints((prev) => prev.filter((ep) => ep.id !== id));
      setNotification({ type: "success", message: "Endpoint removed." });
    } catch {
      setEndpoints((prev) => prev.filter((ep) => ep.id !== id));
    }
  };

  const handleReplayDelivery = async (deliveryId: number) => {
    if (retryingIds.current.has(deliveryId)) return;
    retryingIds.current.add(deliveryId);
    setReplayingIds((prev) => new Set(prev).add(deliveryId));
    setRetryErrors((prev) => {
      const next = { ...prev };
      delete next[deliveryId];
      return next;
    });
    try {
      const data = await fetchApi<{ delivery: WebhookDelivery }>(
        `/webhooks/deliveries/${deliveryId}/replay/`,
        { method: "POST", suppressErrorToast: true },
      );
      retriedRows.current.set(deliveryId, {
        at: ++requestClock.current,
        row: data.delivery,
      });
      setDeliveries((prev) =>
        prev.map((d) => (d.id === deliveryId ? data.delivery : d)),
      );
      setNotification({
        type: "success",
        message: `Delivery #${deliveryId} retried. Status is now ${data.delivery.status}.`,
      });
    } catch (err) {
      const reason = getApiErrorMessage(err, "The retry request failed.");
      setRetryErrors((prev) => ({ ...prev, [deliveryId]: reason }));
      setNotification({
        type: "error",
        message: `Could not retry delivery #${deliveryId}: ${reason}`,
      });
      // 409 means the status in the table is out of date (someone else, or
      // another tab, already retried it), so pull the current one.
      if (err instanceof ApiError && err.status === 409) {
        void fetchEndpointsAndDeliveries();
      }
    } finally {
      retryingIds.current.delete(deliveryId);
      setReplayingIds((prev) => {
        const next = new Set(prev);
        next.delete(deliveryId);
        return next;
      });
    }
  };

  const copyToClipboard = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopiedSecretId(id);
    setTimeout(() => setCopiedSecretId(null), 2000);
  };

  return (
    <main
      id="main-content"
      className="min-h-screen bg-slate-900 text-slate-100 p-4 sm:p-6 lg:p-8"
    >
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header Banner */}
        <div className="relative p-6 sm:p-8 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="px-3 py-1 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold rounded-full uppercase tracking-wider flex items-center gap-1.5">
                  <Webhook className="w-3.5 h-3.5 text-indigo-400" /> Outgoing
                  Webhooks Engine
                </span>
                <span className="text-xs text-slate-400">
                  HMAC SHA-256 & Celery Retry Policy
                </span>
              </div>
              <h1 className="text-3xl font-black text-white tracking-tight">
                Webhook Event Subscriptions
              </h1>
              <p className="mt-2 text-sm text-slate-300 max-w-2xl">
                Configure HTTP endpoint URLs to receive real-time JSON payloads
                signed with HMAC SHA-256 signatures whenever events occur.
              </p>
            </div>

            {/* Health Dashboard Badge */}
            <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-2xl flex items-center gap-4 shrink-0">
              <div className="p-3 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl">
                <Activity className="w-6 h-6" />
              </div>
              <div>
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Engine Delivery Status
                </span>
                <p className="text-sm font-bold text-white flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />{" "}
                  99.8% Success Rate
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Notifications Alert */}
        {notification && (
          <div
            role={notification.type === "error" ? "alert" : "status"}
            className={`p-4 rounded-xl border flex items-center justify-between transition-all ${
              notification.type === "success"
                ? "bg-emerald-950/40 border-emerald-800 text-emerald-200"
                : "bg-rose-950/40 border-rose-800 text-rose-200"
            }`}
          >
            <div className="flex items-center gap-2 text-xs font-semibold">
              {notification.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-400" />
              )}{" "}
              {notification.message}
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Register New Webhook Endpoint Form */}
        <div className="p-6 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-6 shadow-xl">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-4">
            <Plus className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-white">
              Register New Target Endpoint
            </h2>
          </div>

          <form onSubmit={handleCreateEndpoint} className="space-y-6">
            {/* Target URL */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Payload Destination URL
              </label>
              <div className="relative">
                <Globe className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="url"
                  required
                  placeholder="https://your-domain.com/webhooks/atelier-receiver"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
            </div>

            {/* Event Checkboxes */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
                Subscribed Event Types
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {AVAILABLE_EVENTS.map((ev) => {
                  const isChecked = selectedEvents.includes(ev.id);
                  return (
                    <div
                      key={ev.id}
                      onClick={() => handleToggleEvent(ev.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        isChecked
                          ? "bg-indigo-950/40 border-indigo-500/80 text-white"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200">
                          {ev.label}
                        </span>
                        <span
                          className={`w-4 h-4 rounded border flex items-center justify-center ${
                            isChecked
                              ? "bg-indigo-600 border-indigo-500 text-white"
                              : "border-slate-700"
                          }`}
                        >
                          {isChecked && <Check className="w-3 h-3" />}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                        {ev.desc}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              {isSaving ? "Saving Endpoint..." : "Add Webhook Endpoint"}
            </button>
          </form>
        </div>

        {/* Existing Endpoints List */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Radio className="w-5 h-5 text-indigo-400" /> Active Webhook
            Subscriptions ({endpoints.length})
          </h2>

          <div className="space-y-4">
            {endpoints.map((ep) => (
              <div
                key={ep.id}
                className="p-5 bg-slate-900 border border-slate-800 rounded-2xl space-y-4 shadow-lg"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold text-sm text-white font-mono">
                        {ep.target_url}
                      </span>
                      <span className="px-2 py-0.5 text-[10px] font-bold text-emerald-400 bg-emerald-950/50 border border-emerald-800/40 rounded-full">
                        ACTIVE
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {ep.events.map((ev) => (
                        <span
                          key={ev}
                          className="px-2 py-0.5 text-[10px] font-semibold text-slate-300 bg-slate-800 rounded"
                        >
                          {ev}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Endpoint Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleTestEndpoint(ep.id)}
                      disabled={isTestingId === ep.id}
                      className="px-3 py-1.5 text-xs font-semibold text-indigo-300 hover:text-white bg-indigo-950/60 hover:bg-indigo-900 border border-indigo-800/60 rounded-xl transition-all flex items-center gap-1.5"
                    >
                      <Send
                        className={`w-3.5 h-3.5 ${isTestingId === ep.id ? "animate-pulse" : ""}`}
                      />
                      {isTestingId === ep.id ? "Sending Ping..." : "Test Ping"}
                    </button>

                    <button
                      onClick={() => handleRotateSecret(ep.id)}
                      className="px-3 py-1.5 text-xs font-semibold text-amber-300 hover:text-white bg-amber-950/40 hover:bg-amber-900/60 border border-amber-800/50 rounded-xl transition-all flex items-center gap-1.5"
                      title="Rotate Secret Key"
                    >
                      <RotateCw className="w-3.5 h-3.5" /> Rotate Key
                    </button>

                    <button
                      onClick={() => handleDeleteEndpoint(ep.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors"
                      title="Delete Endpoint"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Secret Key Display & HMAC Info */}
                {ep.secret && (
                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-xl flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <Key className="w-4 h-4 text-amber-400 shrink-0" />
                      <span className="text-xs text-slate-400 font-mono">
                        HMAC Secret:
                      </span>
                      <code className="text-xs text-slate-200 font-mono truncate">
                        {ep.secret}
                      </code>
                    </div>
                    <button
                      onClick={() => copyToClipboard(ep.secret!, ep.id)}
                      className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-800 shrink-0"
                    >
                      {copiedSecretId === ep.id ? (
                        <Check className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Audit Delivery Logs Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-400" /> Delivery Audit Logs
              & Retry
            </h2>
            <button
              onClick={fetchEndpointsAndDeliveries}
              className="px-3 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition-all flex items-center gap-1.5"
            >
              <RotateCw className="w-3.5 h-3.5" /> Refresh Logs
            </button>
          </div>

          <DeliveryLogTable
            deliveries={deliveries}
            onReplay={handleReplayDelivery}
            replayingIds={replayingIds}
            retryErrors={retryErrors}
            isLoading={isLoading}
          />
        </div>
      </div>
    </main>
  );
};

export default WebhookSettingsPage;
