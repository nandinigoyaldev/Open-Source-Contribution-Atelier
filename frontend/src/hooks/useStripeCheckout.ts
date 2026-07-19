import { useState } from "react";
import { fetchApi } from "../lib/api";
import toast from "react-hot-toast";

export function useStripeCheckout() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subscribe = async (planId: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi("/billing/checkout/", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId }),
      });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        throw new Error("No redirect URL returned from checkout endpoint");
      }
    } catch (err: any) {
      const msg = err.message || "Failed to initiate checkout session";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const openPortal = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi("/billing/portal/", {
        method: "POST",
      });
      if (data.url) {
        window.location.href = data.url;
      } else {
        throw new Error("No redirect URL returned from portal endpoint");
      }
    } catch (err: any) {
      const msg = err.message || "Failed to open billing portal";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return {
    subscribe,
    openPortal,
    loading,
    error,
  };
}
