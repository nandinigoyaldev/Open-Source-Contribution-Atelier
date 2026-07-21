import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

interface ContentReport {
  id: number;
  reporter_username: string;
  content_type_str: string;
  content_summary: string;
  category: string;
  description: string;
  status: "PENDING" | "APPROVED" | "DISMISSED";
  action_taken: "NONE" | "HIDDEN" | "REMOVED";
  created_at: string;
}

export function ModerationDashboard() {
  const [filter, setFilter] = useState("PENDING");
  const [selectedReport, setSelectedReport] = useState<ContentReport | null>(
    null,
  );
  const [isActionLoading, setIsActionLoading] = useState(false);

  const {
    data: reports = [],
    refetch,
    isLoading,
  } = useQuery<ContentReport[]>({
    queryKey: ["moderationReports", filter],
    queryFn: async () => {
      const response = await fetchApi(`/moderation/reports/?status=${filter}`);
      return Array.isArray(response) ? response : response.results || [];
    },
  });

  const handleAction = async (status: "APPROVED" | "DISMISSED") => {
    if (!selectedReport) return;
    setIsActionLoading(true);
    try {
      await fetchApi(`/moderation/reports/${selectedReport.id}/action/`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      setSelectedReport(null);
      refetch();
    } catch (err) {
      console.error("Action failed", err);
      alert("Failed to process action");
    } finally {
      setIsActionLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-surface dark:bg-[#0a0908] text-black dark:text-white transition-colors duration-200">
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 pt-24 space-y-8">
        <div className="flex flex-col space-y-4">
          <h1 className="text-4xl font-black tracking-tight uppercase border-b-4 border-black dark:border-[#2e2924] pb-4 inline-block">
            Moderation Dashboard
          </h1>
          <p className="text-lg font-medium text-black/70 dark:text-white/70 max-w-2xl">
            Review community reports and moderate inappropriate content.
          </p>
        </div>

        <div className="flex gap-4 border-b-2 border-black/10 dark:border-white/10 pb-4">
          {["PENDING", "APPROVED", "DISMISSED", "ALL"].map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-6 py-2 font-bold rounded-lg border-2 border-black dark:border-[#2e2924] transition-all ${
                filter === status
                  ? "bg-primary text-black shadow-card hover:-translate-y-1"
                  : "bg-surface dark:bg-[#1a1816] hover:bg-black/5 dark:hover:bg-white/5"
              }`}
            >
              {status}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924]">
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
              Reports
              <span className="bg-primary text-black text-sm px-2 py-1 rounded-full">
                {reports.length}
              </span>
            </h2>

            {isLoading ? (
              <div className="text-center py-10 font-bold opacity-50 animate-pulse">
                Loading reports...
              </div>
            ) : reports.length === 0 ? (
              <div className="text-center py-10 font-bold opacity-50">
                No {filter.toLowerCase()} reports found.
              </div>
            ) : (
              <div className="space-y-4">
                {reports.map((report) => (
                  <div
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                    className={`p-4 border-2 border-black rounded-lg cursor-pointer transition-all ${
                      selectedReport?.id === report.id
                        ? "bg-primary text-black shadow-card-sm -translate-y-1"
                        : "bg-surface hover:bg-black/5 dark:bg-[#2e2924] dark:border-black"
                    }`}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="font-bold text-lg">{report.category}</h3>
                      <span className="text-xs uppercase font-bold px-2 py-1 bg-black/10 dark:bg-white/10 rounded">
                        {report.status}
                      </span>
                    </div>
                    <p className="text-sm opacity-70 mb-2 truncate">
                      {report.content_summary}
                    </p>
                    <p className="text-xs font-bold opacity-50">
                      By @{report.reporter_username} •{" "}
                      {new Date(report.created_at).toLocaleDateString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedReport && (
            <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924] flex flex-col h-full">
              <h2 className="text-2xl font-bold mb-6 border-b-2 border-black/10 pb-4">
                Report Details
              </h2>

              <div className="space-y-6 flex-1">
                <div>
                  <h3 className="text-xs font-bold uppercase opacity-50 mb-1">
                    Category
                  </h3>
                  <p className="font-bold text-xl">{selectedReport.category}</p>
                </div>

                <div>
                  <h3 className="text-xs font-bold uppercase opacity-50 mb-1">
                    Description
                  </h3>
                  <p className="p-4 bg-surface dark:bg-[#0a0908] border-2 border-black/10 rounded-lg whitespace-pre-wrap">
                    {selectedReport.description || "No description provided."}
                  </p>
                </div>

                <div>
                  <h3 className="text-xs font-bold uppercase opacity-50 mb-1">
                    Reported Content ({selectedReport.content_type_str})
                  </h3>
                  <p className="p-4 bg-surface dark:bg-[#0a0908] border-2 border-black/10 rounded-lg whitespace-pre-wrap font-mono text-sm">
                    {selectedReport.content_summary}
                  </p>
                </div>
              </div>

              {selectedReport.status === "PENDING" && (
                <div className="flex gap-4 mt-8 pt-6 border-t-2 border-black/10">
                  <button
                    onClick={() => handleAction("DISMISSED")}
                    disabled={isActionLoading}
                    className="flex-1 py-3 font-black uppercase border-2 border-black rounded-lg hover:bg-black/5 transition-all"
                  >
                    Dismiss Report
                  </button>
                  <button
                    onClick={() => handleAction("APPROVED")}
                    disabled={isActionLoading}
                    className="flex-1 py-3 bg-red-500 text-white font-black uppercase border-2 border-black rounded-lg hover:-translate-y-1 shadow-card transition-all"
                  >
                    Approve & Hide Content
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default ModerationDashboard;
