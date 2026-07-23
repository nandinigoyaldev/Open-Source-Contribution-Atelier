import React, { useState } from "react";
import { CreditCard, Calendar, ShieldAlert } from "lucide-react";
import { useStripeCheckout } from "../../hooks/useStripeCheckout";
import { fetchApi } from "../../lib/api";
import toast from "react-hot-toast";

interface SubscriptionData {
  active: boolean;
  status: string;
  current_period_end: string | null;
  plan_name: string | null;
}

interface SubscriptionStatusProps {
  subscription: SubscriptionData;
  onRefresh: () => void;
}

export function SubscriptionStatus({
  subscription,
  onRefresh,
}: SubscriptionStatusProps) {
  const { openPortal, loading: portalLoading } = useStripeCheckout();
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [canceling, setCanceling] = useState(false);

  const handleCancel = async () => {
    setCanceling(true);
    try {
      await fetchApi("/billing/cancel/", {
        method: "POST",
      });
      toast.success("Subscription canceled successfully");
      setShowCancelModal(false);
      onRefresh();
    } catch (err: any) {
      toast.error(err.message || "Failed to cancel subscription");
    } finally {
      setCanceling(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-500";
      case "trialing":
        return "bg-blue-100 text-blue-800 border-blue-500";
      case "past_due":
        return "bg-red-100 text-red-800 border-red-500";
      case "canceled":
        return "bg-gray-100 text-gray-800 border-gray-500";
      default:
        return "bg-gray-100 text-gray-800 border-gray-500";
    }
  };

  return (
    <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card mb-8">
      <h2 className="font-display text-2xl font-black uppercase text-black dark:text-white mb-6">
        Current Subscription
      </h2>

      {subscription.active ? (
        <div className="space-y-6">
          {/* Plan Meta */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="p-4 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
              <span className="text-xs text-gray-500 dark:text-[#c4bbae] block font-bold uppercase mb-1">
                Plan
              </span>
              <span className="font-black text-lg text-black dark:text-white uppercase">
                {subscription.plan_name}
              </span>
            </div>

            <div className="p-4 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
              <span className="text-xs text-gray-500 dark:text-[#c4bbae] block font-bold uppercase mb-1">
                Status
              </span>
              <span
                className={`inline-block px-2.5 py-0.5 text-xs font-black uppercase border-2 rounded-full ${getStatusBadge(subscription.status)}`}
              >
                {subscription.status}
              </span>
            </div>

            {subscription.current_period_end && (
              <div className="p-4 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
                <span className="text-xs text-gray-500 dark:text-[#c4bbae] block font-bold uppercase mb-1">
                  Next Billing Date
                </span>
                <span className="font-bold text-sm text-black dark:text-white flex items-center gap-1.5 mt-0.5">
                  <Calendar size={16} className="text-primary" />
                  {new Date(
                    subscription.current_period_end,
                  ).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-4 pt-4 border-t-2 border-dashed border-gray-200 dark:border-[#2e2924]">
            <button
              onClick={openPortal}
              disabled={portalLoading}
              className="flex items-center gap-2 px-5 py-3 rounded-xl border-4 border-black dark:border-[#2e2924] bg-primary text-black font-black uppercase text-sm shadow-card hover:bg-opacity-95 active:translate-y-[2px] active:shadow-none transition-all disabled:opacity-50"
            >
              <CreditCard size={18} />
              {portalLoading ? "Loading..." : "Manage Billing & Payment"}
            </button>

            {subscription.status !== "canceled" && (
              <button
                onClick={() => setShowCancelModal(true)}
                className="px-5 py-3 rounded-xl border-4 border-black dark:border-[#2e2924] bg-red-100 hover:bg-red-200 text-red-700 font-black uppercase text-sm shadow-card hover:shadow-card active:translate-y-[2px] active:shadow-none transition-all"
              >
                Cancel Subscription
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-8">
          <p className="text-gray-500 dark:text-[#c4bbae] font-bold mb-6">
            You do not have an active premium subscription. Unlock templates,
            Tone Coach, and team playgrounds today!
          </p>
          <a
            href="/pricing"
            className="inline-block px-6 py-3 rounded-xl border-4 border-black dark:border-[#2e2924] bg-primary text-black font-black uppercase text-sm shadow-card hover:translate-y-[-1px] transition-all"
          >
            View Subscription Plans
          </a>
        </div>
      )}

      {/* Cancellation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card animate-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3 text-red-600 mb-4">
              <ShieldAlert size={36} />
              <h3 className="font-display text-xl font-black uppercase">
                Cancel Subscription?
              </h3>
            </div>

            <p className="text-sm text-gray-600 dark:text-[#c4bbae] mb-4 font-bold">
              Are you sure you want to cancel your premium subscription? By
              canceling, you will lose:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-xs text-gray-500 dark:text-[#a8a095] mb-6 font-bold">
              <li>Access to premium path modules & challenge verifications</li>
              <li>AI Maintainer Reply Tone Coach dashboard</li>
              <li>Collaborative playgrounds with unlimited teammates</li>
              <li>Sponsor bounty claims priority access</li>
            </ul>

            {subscription.current_period_end && (
              <div className="p-3 rounded-xl border-2 border-black dark:border-[#2e2924] bg-yellow-50 dark:bg-yellow-950/20 text-yellow-800 dark:text-yellow-400 text-xs font-bold mb-6">
                Note: You can still use Pro features during the grace period
                until{" "}
                {new Date(subscription.current_period_end).toLocaleDateString()}
                .
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowCancelModal(false)}
                className="px-4 py-2 border-2 border-black dark:border-[#2e2924] rounded-lg font-bold text-sm text-gray-700 dark:text-[#c4bbae]"
              >
                No, Keep it
              </button>
              <button
                onClick={handleCancel}
                disabled={canceling}
                className="px-4 py-2 border-2 border-black dark:border-[#2e2924] bg-red-600 text-white rounded-lg font-black uppercase text-sm hover:bg-red-700 disabled:opacity-50"
              >
                {canceling ? "Canceling..." : "Yes, Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
