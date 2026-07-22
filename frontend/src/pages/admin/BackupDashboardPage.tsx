import React, { useState, useEffect } from "react";
import { Loader2, RefreshCw, Database } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fetchApi } from "../../lib/api";
import { format } from "date-fns";
import { toast } from "react-hot-toast";

interface BackupVerification {
  id: number;
  backup_timestamp: string;
  verification_timestamp: string;
  size_bytes: number;
  status: "success" | "failed";
  logs: string;
}

export default function BackupDashboardPage() {
  const [data, setData] = useState<BackupVerification[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const response = await fetchApi("/api/monitoring/backups/");
      setData(response.results || response);
    } catch (error) {
      toast.error("Failed to fetch backup verification history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleVerifyNow = async () => {
    if (
      !confirm(
        "This will trigger a manual backup verification in the background. Continue?",
      )
    ) {
      return;
    }
    try {
      setVerifying(true);
      await fetchApi("/api/monitoring/backups/verify_now/", { method: "POST" });
      toast.success(
        "Backup verification started in background. Check back later for results.",
      );
    } catch (error) {
      toast.error("Failed to trigger verification");
    } finally {
      setVerifying(false);
    }
  };

  const chartData = data
    .slice()
    .reverse()
    .map((item) => ({
      time: format(new Date(item.verification_timestamp), "MMM dd"),
      sizeMB: item.size_bytes ? (item.size_bytes / 1024 / 1024).toFixed(2) : 0,
      status: item.status,
    }));

  const latest = data[0];

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Backup Monitoring
          </h1>
          <p className="text-gray-400 mt-2">
            Monitor database backup integrity and history.
          </p>
        </div>
        <button
          onClick={handleVerifyNow}
          disabled={verifying}
          className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50"
        >
          {verifying ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Verify Latest Backup Now
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        </div>
      ) : (
        <div className="grid gap-6">
          <div className="grid gap-6 md:grid-cols-3">
            <div className="p-6 bg-[#1a1e27] border border-gray-800 rounded-lg shadow-sm">
              <h3 className="font-semibold mb-2 text-gray-200">
                Latest Backup Status
              </h3>
              {latest ? (
                <div>
                  <div
                    className={`text-2xl font-bold ${latest.status === "success" ? "text-green-500" : "text-red-500"}`}
                  >
                    {latest.status === "success" ? "Verified OK" : "Failed"}
                  </div>
                  <p className="text-sm text-gray-400 mt-2">
                    Verified at:{" "}
                    {format(new Date(latest.verification_timestamp), "PPpp")}
                  </p>
                </div>
              ) : (
                <p className="text-gray-400">No verifications found</p>
              )}
            </div>

            <div className="p-6 bg-[#1a1e27] border border-gray-800 rounded-lg shadow-sm">
              <h3 className="font-semibold mb-2 text-gray-200">
                Latest Backup Size
              </h3>
              <div className="text-2xl font-bold text-white">
                {latest?.size_bytes
                  ? `${(latest.size_bytes / 1024 / 1024).toFixed(2)} MB`
                  : "N/A"}
              </div>
            </div>

            <div className="p-6 bg-[#1a1e27] border border-gray-800 rounded-lg shadow-sm">
              <h3 className="font-semibold mb-2 text-gray-200">
                Total Verifications
              </h3>
              <div className="text-2xl font-bold text-white">
                {data.length}{" "}
                <span className="text-sm font-normal text-gray-400">
                  (30 days)
                </span>
              </div>
            </div>
          </div>

          <div className="p-6 bg-[#1a1e27] border border-gray-800 rounded-lg shadow-sm">
            <h3 className="font-semibold mb-6 text-gray-200">
              Backup Size History (Last 30 Days)
            </h3>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9ca3af" />
                  <YAxis unit=" MB" stroke="#9ca3af" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1f2937",
                      border: "1px solid #374151",
                      color: "#fff",
                    }}
                    itemStyle={{ color: "#fff" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="sizeMB"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.2}
                    name="Backup Size (MB)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {latest?.status === "failed" && (
            <div className="p-4 bg-red-900/50 border border-red-500 rounded-lg shadow-sm text-red-200 flex items-start gap-3">
              <Database className="h-5 w-5 mt-0.5 text-red-400" />
              <div>
                <h4 className="font-semibold">Latest Verification Failed</h4>
                <pre className="whitespace-pre-wrap mt-2 text-sm text-red-300 font-mono overflow-x-auto">
                  {latest.logs}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
