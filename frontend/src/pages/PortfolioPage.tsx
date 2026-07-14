import React, { useState, useEffect } from "react";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import {
  FileDown,
  Award,
  TrendingUp,
  Share2,
  CheckCircle,
  ShieldCheck,
  Zap,
} from "lucide-react";
import toast from "react-hot-toast";

interface Portfolio {
  id: string;
  format: string;
  status: string;
  created_at: string;
  file?: string;
  error_message?: string;
}

interface DownloadResponse {
  download_url?: string;
}

export default function PortfolioPage() {
  const { user } = useAuth();
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  // Form state
  const [selectedFormat, setSelectedFormat] = useState<"pdf" | "html">("pdf");
  const [sections, setSections] = useState({
    badges: true,
    certificates: true,
    stats: true,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const portData = (await fetchApi("/portfolio/reports/")) as Portfolio[];
      setPortfolios(portData);
    } catch (error) {
      console.error("Error fetching portfolio data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      await fetchApi("/portfolio/reports/generate/", {
        method: "POST",
        body: JSON.stringify({
          format: selectedFormat,
          sections_included: sections,
        }),
      });
      toast.success("Portfolio generation queued successfully!");
      fetchData();
    } catch (error) {
      toast.error("Failed to generate portfolio.");
      console.error("Error generating portfolio", error);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (id: string) => {
    try {
      const res = (await fetchApi(
        `/portfolio/reports/${id}/download/`,
      )) as DownloadResponse;
      if (res.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (error) {
      toast.error("Failed to download portfolio.");
      console.error("Error downloading portfolio", error);
    }
  };

  const copyShareableLink = () => {
    const link = `${window.location.origin}/u/${user?.username}`;
    navigator.clipboard.writeText(link);
    toast.success("Public profile verification link copied!");
  };

  if (loading) {
    return (
      <div className="p-8 font-black text-center">
        Loading Portfolio Data...
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-10 animate-fade-in select-none">
      {/* Title Header */}
      <div className="border-4 border-black bg-white p-6 rounded-2xl shadow-card dark:bg-[#1a191f] dark:border-white/10 dark:shadow-none">
        <h1 className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white uppercase tracking-tight flex items-center gap-3">
          <Award size={36} className="text-[#8884d8]" /> Contributor Credentials
        </h1>
        <p className="text-sm font-bold text-slate-500 dark:text-slate-400 mt-2 leading-relaxed max-w-2xl">
          Forge certified multi-page PDF/HTML portfolios of your coding
          achievements, or share a verified digital credential card with hiring
          managers to prove your open source mastery.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-8 items-start">
        {/* Left Side: Configuration & History */}
        <div className="space-y-8">
          {/* Configuration Forge */}
          <div className="border-4 border-black bg-white p-6 sm:p-8 rounded-2xl shadow-card dark:bg-[#1a191f] dark:border-white/10 dark:shadow-none space-y-6">
            <h2 className="text-xl font-black uppercase tracking-tight text-slate-950 dark:text-white border-b-2 border-black/5 dark:border-white/5 pb-2">
              Portfolio Forge
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="block text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Export Format
                </label>
                <select
                  className="w-full p-3 border-2 border-black rounded-xl font-bold bg-white text-black focus:outline-none dark:bg-[#121216] dark:text-white dark:border-white/15"
                  value={selectedFormat}
                  onChange={(e) =>
                    setSelectedFormat(e.target.value as "pdf" | "html")
                  }
                >
                  <option value="pdf">PDF Document (.pdf)</option>
                  <option value="html">HTML Webpage (.html)</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Credential Details
                </label>
                <div className="space-y-2 pt-1.5">
                  <label className="flex items-center gap-2 cursor-pointer font-bold text-sm">
                    <input
                      type="checkbox"
                      checked={sections.badges}
                      onChange={(e) =>
                        setSections({ ...sections, badges: e.target.checked })
                      }
                      className="w-4 h-4 accent-[#8884d8] rounded cursor-pointer"
                    />
                    <span>Include Achievements & Badges</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer font-bold text-sm">
                    <input
                      type="checkbox"
                      checked={sections.certificates}
                      onChange={(e) =>
                        setSections({
                          ...sections,
                          certificates: e.target.checked,
                        })
                      }
                      className="w-4 h-4 accent-[#8884d8] rounded cursor-pointer"
                    />
                    <span>Include Graduation Certificates</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer font-bold text-sm">
                    <input
                      type="checkbox"
                      checked={sections.stats}
                      onChange={(e) =>
                        setSections({ ...sections, stats: e.target.checked })
                      }
                      className="w-4 h-4 accent-[#8884d8] rounded cursor-pointer"
                    />
                    <span>Include Platform Statistics</span>
                  </label>
                </div>
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={generating}
              className="w-full py-4 px-6 border-2 border-black bg-[#C3C0FF] text-black font-black uppercase tracking-wider rounded-xl shadow-card-sm hover:-translate-y-0.5 hover:shadow-card active:translate-y-0 active:shadow-none transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {generating ? "Forging Document..." : "Forge Portfolio Report"}
            </button>
          </div>

          {/* History of forged documents */}
          <div className="border-4 border-black bg-white p-6 rounded-2xl shadow-card dark:bg-[#1a191f] dark:border-white/10 dark:shadow-none">
            <h2 className="text-xl font-black uppercase tracking-tight text-slate-950 dark:text-white border-b-2 border-black/5 dark:border-white/5 pb-2 mb-4">
              Forged Portfolios History
            </h2>

            {portfolios.length === 0 ? (
              <div className="text-slate-400 font-bold text-center py-8 text-sm">
                No reports forged yet. Set your preferences above to begin!
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b-2 border-black dark:border-slate-800 text-[10px] font-black uppercase tracking-widest text-slate-400">
                      <th className="pb-2">Date</th>
                      <th className="pb-2">Format</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-black/5 dark:divide-white/5">
                    {portfolios.map((port) => (
                      <tr
                        key={port.id}
                        className="text-xs font-bold text-slate-700 dark:text-slate-350"
                      >
                        <td className="py-3">
                          {new Date(port.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3">
                          <span className="uppercase font-black text-slate-800 dark:text-white bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-black/10">
                            {port.format}
                          </span>
                        </td>
                        <td className="py-3">
                          {port.status === "completed" && (
                            <span className="text-green-600 bg-green-50 dark:bg-green-950/20 dark:text-green-400 px-2 py-0.5 rounded border border-green-500/20">
                              Completed
                            </span>
                          )}
                          {port.status === "failed" && (
                            <span className="text-red-600 bg-red-50 dark:bg-red-950/20 dark:text-red-400 px-2 py-0.5 rounded border border-red-500/20">
                              Failed
                            </span>
                          )}
                          {(port.status === "pending" ||
                            port.status === "processing") && (
                            <span className="text-amber-600 bg-amber-50 dark:bg-amber-950/20 dark:text-amber-400 px-2 py-0.5 rounded border border-amber-500/20 animate-pulse">
                              Processing...
                            </span>
                          )}
                        </td>
                        <td className="py-3 text-right">
                          {port.status === "completed" && (
                            <button
                              onClick={() => handleDownload(port.id)}
                              className="px-3 py-1 bg-white border-2 border-black rounded-lg text-[10px] font-black uppercase hover:-translate-y-0.5 shadow-card-xs transition-all flex items-center gap-1 ml-auto cursor-pointer dark:bg-slate-800 dark:text-white dark:border-slate-700"
                            >
                              <FileDown size={12} /> Download
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: verified developer card preview */}
        <aside className="space-y-6">
          <span className="block text-xs font-black uppercase tracking-widest text-slate-400 pl-1">
            Live Preview: Shareable Credential
          </span>

          <div className="border-4 border-black bg-white rounded-2xl shadow-card dark:bg-[#1a191f] dark:border-white/10 dark:shadow-none overflow-hidden relative select-none">
            {/* Header Stamp */}
            <div className="bg-[#C3C0FF] p-4 border-b-4 border-black dark:border-white/10 flex items-center justify-between">
              <span className="text-xs font-black uppercase tracking-wider text-black">
                Verified Credential Card
              </span>
              <ShieldCheck size={18} className="text-black" />
            </div>

            {/* Main developer info */}
            <div className="p-6 space-y-6 relative">
              {/* Ribbon check */}
              <div className="absolute right-4 top-4 border-4 border-black bg-green-400 text-black text-[9px] font-black uppercase px-2 py-1 rotate-12 shadow-card-xs">
                Verified Profile
              </div>

              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full border-2 border-black bg-[#ffb5e8] flex items-center justify-center font-black text-sm uppercase">
                  {user?.username?.slice(0, 2).toUpperCase() || "CN"}
                </div>
                <div>
                  <h3 className="font-black text-lg text-slate-900 dark:text-white">
                    @{user?.username || "contributor"}
                  </h3>
                  <span className="text-[10px] font-black text-[#8884d8] uppercase tracking-wider">
                    Level {user?.is_staff ? "Maintainer" : "Developer"}
                  </span>
                </div>
              </div>

              {/* Verified Achievements Shelf */}
              <div className="border-t-2 border-dashed border-black/15 pt-4 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-400 font-bold uppercase tracking-wider">
                    Certificates Issued
                  </span>
                  <span className="font-black text-slate-800 dark:text-white flex items-center gap-1">
                    <CheckCircle size={12} className="text-green-500" />{" "}
                    Verified Graduate
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-400 font-bold uppercase tracking-wider">
                    Platform Rank
                  </span>
                  <span className="font-black text-slate-800 dark:text-white flex items-center gap-1">
                    <TrendingUp size={12} className="text-[#8884d8]" /> Top
                    Contributor
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-400 font-bold uppercase tracking-wider">
                    Weekly Streak
                  </span>
                  <span className="font-black text-slate-800 dark:text-white flex items-center gap-1">
                    <Zap size={12} className="text-amber-500 fill-amber-500" />{" "}
                    Active Coding
                  </span>
                </div>
              </div>

              {/* Embed Badge markdown preview */}
              <div className="bg-slate-50 dark:bg-slate-850 p-3 rounded-xl border border-black/10 text-[10px] font-mono leading-relaxed space-y-1.5">
                <span className="block font-black text-slate-400 uppercase tracking-widest text-[8px]">
                  Markdown Badge for Github README
                </span>
                <input
                  type="text"
                  readOnly
                  value={`[![Verified Profile](https://img.shields.io/badge/Atelier-Verified_Developer-C3C0FF?logo=github&style=flat-square)](${window.location.origin}/u/${user?.username})`}
                  className="w-full p-1.5 border border-black/15 bg-white text-slate-600 dark:bg-[#121216] dark:text-slate-300 dark:border-white/10 rounded font-mono text-[9px] focus:outline-none"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
              </div>

              <button
                onClick={copyShareableLink}
                className="w-full py-2.5 border-2 border-black bg-white text-black font-black uppercase text-xs rounded-xl shadow-card-sm hover:-translate-y-0.5 hover:shadow-card active:translate-y-0 active:shadow-none transition-all flex items-center justify-center gap-2 cursor-pointer dark:bg-slate-800 dark:text-white dark:border-slate-700"
              >
                <Share2 size={14} /> Copy Verification Link
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
