import React, { useState, useEffect } from "react";
import { fetchApi } from "../lib/api";

interface Template {
  id: number;
  name: string;
  description: string;
}

interface Portfolio {
  id: string;
  format: string;
  status: string;
  created_at: string;
  file?: string;
  error_message?: string;
}

export default function PortfolioPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  // Form state
  const [selectedFormat, setSelectedFormat] = useState<"pdf" | "html">("pdf");
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
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
      const [tplData, portData] = await Promise.all([
        fetchApi("/portfolio/templates/"),
        fetchApi("/portfolio/reports/"),
      ]);
      setTemplates(tplData as any);
      if ((tplData as any).length > 0) {
        setSelectedTemplate((tplData as any)[0].id);
      }
      setPortfolios(portData as any);
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
          template_id: selectedTemplate,
          sections_included: sections,
        }),
      });
      // Refresh list to show pending
      fetchData();
    } catch (error) {
      console.error("Error generating portfolio", error);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (id: string) => {
    try {
      const res: any = await fetchApi(`/portfolio/reports/${id}/download/`);
      if (res.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (error) {
      console.error("Error downloading portfolio", error);
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-500 to-indigo-600 bg-clip-text text-transparent">
          Developer Portfolio Generator
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Generate a professional, multi-page portfolio highlighting your
          achievements, stats, and badges on the platform.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Configuration Panel */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 space-y-6">
          <h2 className="text-xl font-semibold">Configuration</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Format</label>
              <select
                className="w-full p-2 border rounded-md dark:bg-gray-900 dark:border-gray-600"
                value={selectedFormat}
                onChange={(e) =>
                  setSelectedFormat(e.target.value as "pdf" | "html")
                }
              >
                <option value="pdf">PDF</option>
                <option value="html">HTML</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Sections to Include
              </label>
              <div className="space-y-2 mt-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={sections.badges}
                    onChange={(e) =>
                      setSections({ ...sections, badges: e.target.checked })
                    }
                    className="rounded text-blue-500"
                  />
                  <span>Badges & Achievements</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={sections.certificates}
                    onChange={(e) =>
                      setSections({
                        ...sections,
                        certificates: e.target.checked,
                      })
                    }
                    className="rounded text-blue-500"
                  />
                  <span>Certificates</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={sections.stats}
                    onChange={(e) =>
                      setSections({ ...sections, stats: e.target.checked })
                    }
                    className="rounded text-blue-500"
                  />
                  <span>Platform Statistics</span>
                </label>
              </div>
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full py-2 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg disabled:opacity-50"
          >
            {generating ? "Generating..." : "Generate Portfolio"}
          </button>
        </div>

        {/* History Panel */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4">Generated Reports</h2>

          {portfolios.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No reports generated yet.
            </div>
          ) : (
            <div className="space-y-4">
              {portfolios.map((port) => (
                <div
                  key={port.id}
                  className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-750 rounded-lg border border-gray-100 dark:border-gray-600"
                >
                  <div>
                    <div className="font-medium">
                      Portfolio ({port.format.toUpperCase()})
                    </div>
                    <div className="text-sm text-gray-500">
                      {new Date(port.created_at).toLocaleDateString()} •{" "}
                      {port.status}
                    </div>
                  </div>
                  <div>
                    {port.status === "completed" && (
                      <button
                        onClick={() => handleDownload(port.id)}
                        className="text-sm px-3 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-200 rounded-md transition-colors"
                      >
                        Download
                      </button>
                    )}
                    {port.status === "failed" && (
                      <span className="text-xs text-red-500 bg-red-100 px-2 py-1 rounded">
                        Failed
                      </span>
                    )}
                    {port.status === "pending" ||
                    port.status === "processing" ? (
                      <span className="text-xs text-yellow-600 bg-yellow-100 px-2 py-1 rounded">
                        Processing...
                      </span>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
