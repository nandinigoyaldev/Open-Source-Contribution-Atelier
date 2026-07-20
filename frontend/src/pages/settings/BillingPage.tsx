import React, { useEffect, useState } from "react";
import { fetchApi } from "../../lib/api";
import { SubscriptionStatus } from "../../components/billing/SubscriptionStatus";
import { Receipt, ArrowRight } from "lucide-react";

export function BillingPage() {
  const [subscription, setSubscription] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchSubscription = async () => {
    try {
      const data = await fetchApi("/billing/status/");
      setSubscription(data);
    } catch (err) {
      console.error("Failed to load subscription status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscription();
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="text-xl font-bold uppercase animate-pulse text-black dark:text-white">
          Loading billing settings...
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white uppercase mb-2">
          Billing Settings
        </h1>
        <p className="text-gray-500 dark:text-[#c4bbae] font-bold">
          Manage your subscription plans, billing details, payments, and view
          invoice history.
        </p>
      </div>

      {subscription && (
        <SubscriptionStatus
          subscription={subscription}
          onRefresh={fetchSubscription}
        />
      )}

      {/* Quick link to Invoice History */}
      <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card flex items-center justify-between hover:bg-gray-50 dark:hover:bg-[#1f1c18] transition-all">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-purple-100 dark:bg-purple-950/30 rounded-xl border-2 border-black dark:border-[#2e2924] text-purple-700 dark:text-purple-400">
            <Receipt size={24} />
          </div>
          <div>
            <h3 className="font-bold text-black dark:text-white text-base">
              Invoices & Billing History
            </h3>
            <p className="text-xs text-gray-500 dark:text-[#c4bbae] font-bold">
              View and download past invoices and receipt statements.
            </p>
          </div>
        </div>

        <a
          href="/settings/invoices"
          className="flex items-center justify-center p-2 rounded-xl border-2 border-black dark:border-[#2e2924] hover:bg-primary hover:text-black transition-all"
        >
          <ArrowRight size={20} />
        </a>
      </div>
    </div>
  );
}

export default BillingPage;
