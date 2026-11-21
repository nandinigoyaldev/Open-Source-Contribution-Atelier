// Types and wording for the admin feature-flag page (GET /feature-flags/).
// The list endpoint only returns counts for targeted users and organizations,
// so nothing here can show who is in a rollout, only how many.

export type FeatureFlagType =
  | "boolean"
  | "percentage"
  | "organization"
  | "user";

export interface FeatureFlagSummary {
  id: number;
  name: string;
  description: string;
  flag_type: FeatureFlagType;
  is_active: boolean;
  kill_switch: boolean;
  default_value: boolean;
  rollout_percentage: number;
  environments: string[];
  applies_in_current_environment: boolean;
  target_users_count: number;
  target_organizations_count: number;
  updated_at: string;
}

export interface RolloutImpact {
  /** Share of users the flag is on for, or null when it depends on a target list. */
  percent: number | null;
  label: string;
}

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? "" : "s"}`;

/** Where the flag can turn on at all. */
export function describeScope(flag: FeatureFlagSummary): string {
  if (!flag.environments.length) return "All environments";
  return flag.environments.join(", ");
}

/** Targeting as counts only. */
export function describeTargets(flag: FeatureFlagSummary): string {
  const parts: string[] = [];
  if (flag.target_users_count)
    parts.push(plural(flag.target_users_count, "user"));
  if (flag.target_organizations_count)
    parts.push(plural(flag.target_organizations_count, "organization"));
  return parts.length ? parts.join(", ") : "No targets";
}

/**
 * Who the flag is on for right now, in the same order the backend evaluates it
 * (apps/feature_flags/services.py evaluate_feature_flag): kill switch, active,
 * environment, target-only flag types, then percentage.
 */
export function describeRollout(flag: FeatureFlagSummary): RolloutImpact {
  if (flag.kill_switch) {
    return { percent: 0, label: "Off everywhere (kill switch engaged)" };
  }
  const fallback = flag.default_value ? 100 : 0;
  if (!flag.is_active) {
    return {
      percent: fallback,
      label: flag.default_value ? "Inactive, default is on" : "Inactive",
    };
  }
  if (!flag.applies_in_current_environment) {
    return { percent: fallback, label: "Not enabled in this environment" };
  }
  if (flag.flag_type === "organization") {
    return {
      percent: null,
      label: `Only ${plural(flag.target_organizations_count, "targeted organization")}`,
    };
  }
  if (flag.flag_type === "user") {
    return {
      percent: null,
      label: `Only ${plural(flag.target_users_count, "targeted user")}`,
    };
  }
  if (flag.flag_type === "percentage" || flag.rollout_percentage > 0) {
    const targets =
      flag.target_users_count || flag.target_organizations_count
        ? `, plus ${describeTargets(flag)}`
        : "";
    return {
      percent: flag.rollout_percentage,
      label: `${flag.rollout_percentage}% of signed-in users${targets}`,
    };
  }
  return { percent: 100, label: "Everyone" };
}
