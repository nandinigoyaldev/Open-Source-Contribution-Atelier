import { useCallback, useEffect, useState } from "react";
import { Flag, Power, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "react-hot-toast";
import { fetchApi } from "../../lib/api";
import { useAuth } from "../../features/auth/AuthContext";
import {
  describeRollout,
  describeScope,
  describeTargets,
  type FeatureFlagSummary,
} from "../../lib/featureFlags";

function statusBadge(flag: FeatureFlagSummary) {
  if (flag.kill_switch)
    return {
      text: "Killed",
      className:
        "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
    };
  if (flag.is_active)
    return {
      text: "Active",
      className:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    };
  return {
    text: "Inactive",
    className: "bg-gray-100 text-gray-600 dark:bg-slate-800 dark:text-gray-400",
  };
}

export function FeatureFlagsPage() {
  const { user, isLoading: authLoading } = useAuth();
  // The API is IsAdminUser; this only avoids a request that will be refused.
  const accessDenied = !authLoading && user?.is_staff !== true;

  const [flags, setFlags] = useState<FeatureFlagSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const loadFlags = useCallback(async () => {
    if (accessDenied) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await fetchApi<FeatureFlagSummary[]>("/feature-flags/", {
        suppressErrorToast: true,
      });
      setFlags(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Could not load feature flags");
    } finally {
      setLoading(false);
    }
  }, [accessDenied]);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  const toggleKillSwitch = async (flag: FeatureFlagSummary) => {
    const engaged = !flag.kill_switch;
    const reason = window.prompt(
      engaged
        ? `Why are you turning "${flag.name}" off everywhere?`
        : `Why is "${flag.name}" safe to turn back on?`,
    );
    if (reason === null) return;
    try {
      setBusyId(flag.id);
      const res = await fetchApi<{ flag: FeatureFlagSummary }>(
        `/feature-flags/${flag.id}/kill-switch/`,
        { method: "POST", body: JSON.stringify({ engaged, reason }) },
      );
      setFlags((prev) =>
        prev.map((f) => (f.id === flag.id ? { ...f, ...res.flag } : f)),
      );
      toast.success(
        engaged
          ? `${flag.name} is now off everywhere`
          : `${flag.name} released`,
      );
    } catch {
      toast.error("Kill switch request failed");
    } finally {
      setBusyId(null);
    }
  };

  if (accessDenied) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <ShieldAlert className="mx-auto h-10 w-10 text-rose-500" />
        <h1 className="mt-4 text-xl font-bold text-gray-900 dark:text-white">
          Administrators only
        </h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Feature flags can only be viewed and changed by staff accounts.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
            <Flag className="h-6 w-6" aria-hidden="true" />
            Feature flags
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Scope and rollout for each flag. Targeted users and organizations
            are shown as counts only.
          </p>
        </div>
        <button
          type="button"
          onClick={loadFlags}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-slate-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-800"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-gray-500" role="status">
          Loading feature flags...
        </p>
      ) : error ? (
        <p className="text-sm text-rose-600" role="alert">
          {error}
        </p>
      ) : flags.length === 0 ? (
        <p className="text-sm text-gray-500">No feature flags yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-800">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-800 text-sm">
            <thead className="bg-gray-50 dark:bg-slate-900">
              <tr className="text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                <th scope="col" className="px-4 py-3">
                  Flag
                </th>
                <th scope="col" className="px-4 py-3">
                  Status
                </th>
                <th scope="col" className="px-4 py-3">
                  Scope
                </th>
                <th scope="col" className="px-4 py-3">
                  Rollout
                </th>
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-slate-800">
              {flags.map((flag) => {
                const badge = statusBadge(flag);
                const rollout = describeRollout(flag);
                return (
                  <tr key={flag.id} data-testid={`flag-row-${flag.name}`}>
                    <td className="px-4 py-3 align-top">
                      <code className="font-semibold text-gray-900 dark:text-white">
                        {flag.name}
                      </code>
                      {flag.description && (
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          {flag.description}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${badge.className}`}
                      >
                        {badge.text}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-top text-gray-700 dark:text-gray-300">
                      <div>{describeScope(flag)}</div>
                      {!flag.applies_in_current_environment && (
                        <div className="text-xs text-amber-600 dark:text-amber-400">
                          Not this environment
                        </div>
                      )}
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {describeTargets(flag)}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top w-64">
                      {rollout.percent !== null && (
                        <div
                          role="progressbar"
                          aria-label={`${flag.name} rollout`}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={rollout.percent}
                          className="h-2 w-full rounded-full bg-gray-200 dark:bg-slate-800 overflow-hidden"
                        >
                          <div
                            className="h-full bg-blue-500"
                            style={{ width: `${rollout.percent}%` }}
                          />
                        </div>
                      )}
                      <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                        {rollout.label}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top text-right">
                      <button
                        type="button"
                        onClick={() => toggleKillSwitch(flag)}
                        disabled={busyId === flag.id}
                        className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold disabled:opacity-50 ${
                          flag.kill_switch
                            ? "border border-gray-300 dark:border-slate-700 text-gray-700 dark:text-gray-200"
                            : "bg-rose-600 hover:bg-rose-700 text-white"
                        }`}
                      >
                        <Power className="h-3.5 w-3.5" aria-hidden="true" />
                        {flag.kill_switch
                          ? "Release kill switch"
                          : "Kill switch"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default FeatureFlagsPage;
