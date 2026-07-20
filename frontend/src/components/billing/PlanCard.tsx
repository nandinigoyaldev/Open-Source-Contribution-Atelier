import React from "react";
import { Check } from "lucide-react";

export interface Plan {
  id: number;
  name: string;
  price: string;
  stripe_price_id: string;
  features: string[];
}

interface PlanCardProps {
  plan: Plan;
  onSubscribe: (planId: number) => void;
  isLoading: boolean;
  isCurrent: boolean;
  isLoggedIn: boolean;
}

export function PlanCard({
  plan,
  onSubscribe,
  isLoading,
  isCurrent,
  isLoggedIn,
}: PlanCardProps) {
  const isFree = parseFloat(plan.price) === 0;

  return (
    <div className="flex flex-col rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card hover:translate-y-[-2px] transition-all">
      <div className="mb-4">
        <span className="inline-block px-3 py-1 text-xs font-black uppercase tracking-wider border-2 border-black dark:border-[#2e2924] rounded-full bg-yellow-300 text-black">
          {plan.name}
        </span>
      </div>

      <div className="mb-6 flex items-baseline">
        <span className="font-display text-4xl font-black text-black dark:text-white">
          ${plan.price}
        </span>
        <span className="text-gray-500 dark:text-[#c4bbae] ml-1 text-sm font-bold">
          /month
        </span>
      </div>

      <p className="text-sm font-bold text-gray-700 dark:text-[#c4bbae] mb-4">
        Includes:
      </p>
      <ul className="space-y-3 mb-8 flex-1">
        {plan.features.map((feature, idx) => (
          <li
            key={idx}
            className="flex items-start gap-2 text-sm text-gray-600 dark:text-[#a8a095]"
          >
            <Check className="text-green-500 shrink-0 mt-0.5" size={16} />
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      {isCurrent ? (
        <div className="w-full text-center py-3 rounded-xl border-2 border-black dark:border-[#2e2924] bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400 font-black uppercase text-sm">
          Current Plan
        </div>
      ) : isFree ? (
        <div className="w-full text-center py-3 rounded-xl border-2 border-black dark:border-[#2e2924] bg-gray-100 dark:bg-[#1f1c18] text-gray-500 dark:text-[#c4bbae] font-black uppercase text-sm">
          Free Forever
        </div>
      ) : (
        <button
          onClick={() =>
            isLoggedIn
              ? onSubscribe(plan.id)
              : (window.location.href = "/login")
          }
          disabled={isLoading}
          className="w-full py-3 rounded-xl border-4 border-black dark:border-[#2e2924] bg-primary text-black font-black uppercase text-sm shadow-card hover:bg-opacity-90 active:translate-y-[2px] active:shadow-none transition-all disabled:opacity-50"
        >
          {isLoading
            ? "Redirecting..."
            : isLoggedIn
              ? "Subscribe"
              : "Log In to Subscribe"}
        </button>
      )}
    </div>
  );
}
