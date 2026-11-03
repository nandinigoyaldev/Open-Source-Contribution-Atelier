import React, { useState } from "react";
import {
  RotateCw,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Eye,
  X,
  Code,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";

export interface WebhookDeliveryLog {
  id: number;
  status_code: number | null;
  response_body: string;
  attempted_at: string;
}

export interface WebhookDelivery {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  status: "pending" | "success" | "failed" | "retrying" | "dead";
  status_code: number | null;
  response_body: string;
  created_at: string;
  logs?: WebhookDeliveryLog[];
}

/** Only these can be retried by hand; the API answers 409 for anything else. */
const isRetryable = (delivery: WebhookDelivery) =>
  delivery.status === "failed" || delivery.status === "dead";

const EMPTY_IDS: ReadonlySet<number> = new Set();

interface DeliveryLogTableProps {
  deliveries: WebhookDelivery[];
  onReplay: (deliveryId: number) => void;
  /** Ids of the deliveries with a retry in flight. */
  replayingIds?: ReadonlySet<number>;
  /** Last retry error per delivery id, shown next to the row's button. */
  retryErrors?: Record<number, string>;
  isLoading?: boolean;
}

export const DeliveryLogTable: React.FC<DeliveryLogTableProps> = ({
  deliveries,
  onReplay,
  replayingIds = EMPTY_IDS,
  retryErrors = {},
  isLoading = false,
}) => {
  const [inspectDelivery, setInspectDelivery] =
    useState<WebhookDelivery | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

  const getStatusBadge = (
    status: WebhookDelivery["status"],
    statusCode: number | null,
  ) => {
    switch (status) {
      case "success":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-800/50 rounded-lg">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {statusCode ? `${statusCode} OK` : "Success"}
          </span>
        );
      case "failed":
      case "dead":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold text-rose-400 bg-rose-950/40 border border-rose-800/50 rounded-lg">
            <XCircle className="w-3.5 h-3.5" />
            {statusCode ? `${statusCode} Failed` : "Failed (DLQ)"}
          </span>
        );
      case "retrying":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold text-amber-400 bg-amber-950/40 border border-amber-800/50 rounded-lg">
            <AlertTriangle className="w-3.5 h-3.5 animate-bounce" />
            Retrying...
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold text-slate-400 bg-slate-800 border border-slate-700 rounded-lg">
            <Clock className="w-3.5 h-3.5" />
            Pending
          </span>
        );
    }
  };

  return (
    <div className="w-full space-y-4">
      {/* Table Container */}
      <div className="w-full bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                <th className="p-4">Delivery ID & Event</th>
                <th className="p-4">Status</th>
                <th className="p-4">HTTP Status</th>
                <th className="p-4">Dispatched At</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {isLoading ? (
                <tr>
                  <td
                    colSpan={5}
                    className="p-8 text-center text-slate-500 font-medium"
                  >
                    Loading delivery audit logs...
                  </td>
                </tr>
              ) : deliveries.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="p-8 text-center text-slate-500 font-medium"
                  >
                    No webhook delivery events recorded yet. Trigger a test ping
                    or event to populate logs.
                  </td>
                </tr>
              ) : (
                deliveries.map((delivery) => (
                  <tr
                    key={delivery.id}
                    className="hover:bg-slate-800/40 transition-colors group"
                  >
                    {/* Delivery ID & Event */}
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-slate-400">
                          #{delivery.id}
                        </span>
                        <span className="px-2 py-0.5 font-mono font-bold text-[11px] text-indigo-300 bg-indigo-950/60 border border-indigo-800/40 rounded">
                          {delivery.event_type}
                        </span>
                      </div>
                    </td>

                    {/* Status Badge */}
                    <td className="p-4">
                      {getStatusBadge(delivery.status, delivery.status_code)}
                    </td>

                    {/* HTTP Code */}
                    <td className="p-4 font-mono font-bold">
                      {delivery.status_code ? (
                        <span
                          className={
                            delivery.status_code >= 200 &&
                            delivery.status_code < 300
                              ? "text-emerald-400"
                              : "text-rose-400"
                          }
                        >
                          {delivery.status_code}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    {/* Dispatched At */}
                    <td className="p-4 text-slate-400">
                      {new Date(delivery.created_at).toLocaleString()}
                    </td>

                    {/* Actions */}
                    <td className="p-4 text-right space-x-2">
                      <button
                        onClick={() => setInspectDelivery(delivery)}
                        className="px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-all inline-flex items-center gap-1"
                        title="View Payload & Response Body"
                      >
                        <Eye className="w-3.5 h-3.5" /> Payload
                      </button>

                      {isRetryable(delivery) &&
                        (confirmingId === delivery.id ? (
                          <span
                            role="group"
                            aria-label={`Confirm retry of delivery ${delivery.id}`}
                            className="inline-flex items-center gap-1.5"
                          >
                            <span className="text-slate-300">
                              Send it again?
                            </span>
                            <button
                              onClick={() => {
                                setConfirmingId(null);
                                onReplay(delivery.id);
                              }}
                              className="px-2.5 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 border border-indigo-400 rounded-lg transition-all"
                            >
                              Confirm retry
                            </button>
                            <button
                              onClick={() => setConfirmingId(null)}
                              className="px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg"
                            >
                              Cancel
                            </button>
                          </span>
                        ) : (
                          <button
                            onClick={() => setConfirmingId(delivery.id)}
                            disabled={replayingIds.has(delivery.id)}
                            aria-label={`Retry delivery ${delivery.id}`}
                            className="px-2.5 py-1.5 text-xs font-bold text-indigo-300 hover:text-white bg-indigo-950/50 hover:bg-indigo-900/70 border border-indigo-800/60 rounded-lg transition-all inline-flex items-center gap-1 active:scale-95 disabled:opacity-50"
                            title="Retry this failed delivery"
                          >
                            <RotateCw
                              className={`w-3.5 h-3.5 ${
                                replayingIds.has(delivery.id)
                                  ? "animate-spin text-indigo-400"
                                  : ""
                              }`}
                            />
                            {replayingIds.has(delivery.id)
                              ? "Retrying..."
                              : "Retry"}
                          </button>
                        ))}
                      {isRetryable(delivery) && retryErrors[delivery.id] && (
                        <p
                          role="alert"
                          className="mt-1.5 text-[11px] font-semibold text-rose-300"
                        >
                          {retryErrors[delivery.id]}
                        </p>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payload & Response Inspection Modal */}
      {inspectDelivery && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fadeIn"
          onClick={() => setInspectDelivery(null)}
        >
          <div
            className="relative w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-5 bg-slate-950 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Code className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-white">
                  Webhook Delivery #{inspectDelivery.id} Details
                </h3>
              </div>
              <button
                onClick={() => setInspectDelivery(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto custom-scrollbar">
              {/* HMAC Signature Info Badge */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-indigo-300 font-semibold">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  HMAC SHA-256 Signed Payload
                </div>
                <span className="font-mono text-slate-400">
                  Header: X-Hub-Signature-256
                </span>
              </div>

              {/* Sent JSON Payload */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Outgoing JSON Payload
                </h4>
                <pre className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-emerald-400 overflow-x-auto">
                  {JSON.stringify(inspectDelivery.payload, null, 2)}
                </pre>
              </div>

              {/* Server Response Body */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Endpoint Response Body
                </h4>
                <pre className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-slate-300 overflow-x-auto max-h-48">
                  {inspectDelivery.response_body ||
                    "No response body received."}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-950 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setInspectDelivery(null)}
                className="px-4 py-2 text-xs font-bold text-slate-300 hover:text-white bg-slate-800 rounded-xl"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
