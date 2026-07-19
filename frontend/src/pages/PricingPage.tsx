import React, { useEffect, useState } from "react";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { useStripeCheckout } from "../hooks/useStripeCheckout";
import { PlanCard, Plan } from "../components/billing/PlanCard";
import { FeatureTable } from "../components/billing/FeatureTable";

export function PricingPage() {
  const { user } = useAuth();
  const isLoggedIn = !!user;
  const { subscribe, loading: stripeLoading } = useStripeCheckout();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [currentPlanName, setCurrentPlanName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch plans
        const plansData = await fetchApi("/billing/plans/");
        setPlans(plansData);

        // Fetch subscription status if logged in
        if (isLoggedIn) {
          const statusData = await fetchApi("/billing/status/");
          setCurrentPlanName(statusData.plan_name);
        }
      } catch (err) {
        console.error("Failed to load plans or status:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [isLoggedIn]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center">
        <div className="text-xl font-bold uppercase tracking-widest animate-pulse text-black dark:text-white">
          Loading pricing tiers...
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      {/* Page Title */}
      <div className="text-center mb-16">
        <h1 className="text-5xl font-black tracking-tight text-black dark:text-white uppercase mb-4">
          Choose Your Level
        </h1>
        <p className="text-lg max-w-2xl mx-auto text-gray-500 dark:text-[#c4bbae] font-bold">
          Level up your Git expertise, collaborate in real-time, unlock premium
          learning paths, and claim Connect Bounties.
        </p>
      </div>

      {/* Plan Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
        {plans.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            onSubscribe={subscribe}
            isLoading={stripeLoading}
            isCurrent={currentPlanName === plan.name}
            isLoggedIn={isLoggedIn}
          />
        ))}
      </div>

      {/* Feature Comparison */}
      <div className="mb-12">
        <h2 className="text-3xl font-black text-black dark:text-white uppercase text-center mb-8">
          Detailed Comparison
        </h2>
        <FeatureTable />
      </div>
    </div>
  );
}

export default PricingPage;
