import React from "react";
import { Check, X } from "lucide-react";

interface FeatureRow {
  name: string;
  free: string | boolean;
  pro: string | boolean;
  team: string | boolean;
}

const COMPARISON_FEATURES: FeatureRow[] = [
  {
    name: "Git Playgrounds / Sandboxes",
    free: "Unlimited",
    pro: "Unlimited",
    team: "Unlimited",
  },
  {
    name: "Curriculum & Challenges",
    free: "Basic Modules",
    pro: "All Modules + Premium Content",
    team: "All Modules + Custom Team Paths",
  },
  {
    name: "Stripe Connect Bounties Claims",
    free: false,
    pro: "Standard Priority",
    team: "High Priority",
  },
  {
    name: "AI Maintainer Reply Tone Coach",
    free: "5 runs / day",
    pro: "Unlimited",
    team: "Unlimited",
  },
  {
    name: "Real-time Collaboration Sandbox",
    free: false,
    pro: "Up to 2 collaborators",
    team: "Unlimited collaborators",
  },
  {
    name: "Deduplication & Dep Graph Tools",
    free: false,
    pro: true,
    team: true,
  },
  {
    name: "Custom Portfolio Page Hosting",
    free: "Basic Theme",
    pro: "All Premium Themes + Domains",
    team: "All Premium Themes + Domains",
  },
  { name: "Monthly Cost", free: "$0", pro: "$19.99", team: "$49.99" },
];

export function FeatureTable() {
  const renderCell = (val: string | boolean) => {
    if (typeof val === "boolean") {
      return val ? (
        <Check className="text-green-500 mx-auto" size={20} />
      ) : (
        <X className="text-red-500 mx-auto" size={20} />
      );
    }
    return (
      <span className="font-bold text-sm text-gray-700 dark:text-[#c4bbae]">
        {val}
      </span>
    );
  };

  return (
    <div className="overflow-x-auto rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card bg-white dark:bg-[#151411]">
      <table className="w-full min-w-[600px] border-collapse text-left">
        <thead>
          <tr className="border-b-4 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
            <th className="p-4 font-black uppercase text-sm text-black dark:text-white">
              Feature
            </th>
            <th className="p-4 text-center font-black uppercase text-sm text-black dark:text-white">
              Free
            </th>
            <th className="p-4 text-center font-black uppercase text-sm text-black dark:text-white">
              Pro
            </th>
            <th className="p-4 text-center font-black uppercase text-sm text-black dark:text-white">
              Team
            </th>
          </tr>
        </thead>
        <tbody className="divide-y-2 divide-black dark:divide-[#2e2924]">
          {COMPARISON_FEATURES.map((row, idx) => (
            <tr
              key={idx}
              className="hover:bg-gray-50 dark:hover:bg-[#1f1c18]/50 transition-colors"
            >
              <td className="p-4 font-bold text-sm text-black dark:text-white">
                {row.name}
              </td>
              <td className="p-4 text-center">{renderCell(row.free)}</td>
              <td className="p-4 text-center">{renderCell(row.pro)}</td>
              <td className="p-4 text-center">{renderCell(row.team)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
