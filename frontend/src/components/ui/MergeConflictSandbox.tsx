import React, { useState } from "react";
import { GitMerge, Check, AlertTriangle, ArrowRight } from "lucide-react";

export function MergeConflictSandbox() {
  const [resolvedStatus, setResolvedStatus] = useState<
    "unresolved" | "current" | "incoming" | "both"
  >("unresolved");
  const [isMerged, setIsMerged] = useState(false);

  const handleResolve = (choice: "current" | "incoming" | "both") => {
    setResolvedStatus(choice);
  };

  const handleMerge = () => {
    if (resolvedStatus !== "unresolved") {
      setIsMerged(true);
    }
  };

  const reset = () => {
    setResolvedStatus("unresolved");
    setIsMerged(false);
  };

  return (
    <div className="w-full rounded-2xl border-4 border-black bg-white shadow-card overflow-hidden dark:bg-[#1f1c18] dark:border-[#2e2924] flex flex-col my-8">
      {/* Header */}
      <div className="bg-accent p-4 border-b-4 border-black dark:bg-[#2e2924] dark:border-black flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitMerge className="text-black dark:text-white" size={24} />
          <h3 className="font-black text-xl text-black dark:text-white uppercase tracking-wider">
            Interactive Conflict Resolution
          </h3>
        </div>
        <span className="text-xs font-black px-3 py-1 bg-white border-2 border-black rounded-full dark:bg-black dark:text-white shadow-card-sm">
          Sandbox Mode
        </span>
      </div>

      <div className="p-6 md:p-8 space-y-8">
        {/* Timeline Visualization */}
        <div className="relative pt-6 pb-2">
          <div className="absolute top-1/2 left-0 w-full h-1 bg-black/20 dark:bg-white/20 -translate-y-1/2 rounded-full" />

          {/* Main Branch */}
          <div className="absolute top-[30%] left-0 w-[60%] h-1 bg-blue-500 rounded-full" />
          {/* Feature Branch */}
          <div className="absolute top-[70%] left-[20%] w-[40%] h-1 bg-green-500 rounded-full" />
          {/* Merge line */}
          <svg
            className="absolute top-[30%] left-[55%] w-[10%] h-[40%] text-green-500 overflow-visible"
            preserveAspectRatio="none"
          >
            <path
              d="M 0,100 C 50,100 50,0 100,0"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
            />
          </svg>

          <div className="flex justify-between relative z-10">
            <div className="flex flex-col items-center gap-2 group">
              <div className="w-6 h-6 rounded-full border-4 border-black bg-blue-500 shadow-card-sm group-hover:scale-125 transition-transform" />
              <span className="text-[10px] font-black font-mono">Init</span>
            </div>
            <div className="flex flex-col items-center gap-2 mt-8 group">
              <div className="w-6 h-6 rounded-full border-4 border-black bg-green-500 shadow-card-sm group-hover:scale-125 transition-transform" />
              <span className="text-[10px] font-black font-mono">
                Feat start
              </span>
            </div>
            <div className="flex flex-col items-center gap-2 group">
              <div className="w-6 h-6 rounded-full border-4 border-black bg-blue-500 shadow-card-sm group-hover:scale-125 transition-transform" />
              <span className="text-[10px] font-black font-mono">
                Main update
              </span>
            </div>
            <div className="flex flex-col items-center gap-2 mt-8 group">
              <div className="w-6 h-6 rounded-full border-4 border-black bg-green-500 shadow-card-sm group-hover:scale-125 transition-transform" />
              <span className="text-[10px] font-black font-mono">
                Feat update
              </span>
            </div>
            <div className="flex flex-col items-center gap-2 group relative">
              <div
                className={`w-8 h-8 rounded-full border-4 border-black shadow-card-sm flex items-center justify-center transition-all duration-500 ${isMerged ? "bg-green-400" : "bg-red-500 animate-pulse"}`}
              >
                {isMerged ? (
                  <Check size={16} className="text-black" />
                ) : (
                  <AlertTriangle size={16} className="text-white" />
                )}
              </div>
              <span className="text-[10px] font-black font-mono absolute top-10 whitespace-nowrap">
                {isMerged ? "Merged!" : "Conflict!"}
              </span>
            </div>
          </div>
        </div>

        <hr className="border-2 border-black/10 dark:border-white/10" />

        {/* Sandbox Area */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-black text-lg">Resolve the conflict</h4>
            {isMerged && (
              <button
                onClick={reset}
                className="text-xs font-black underline hover:text-blue-500"
              >
                Reset Sandbox
              </button>
            )}
          </div>

          {!isMerged ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Conflict Editor view */}
              <div className="rounded-lg border-4 border-black overflow-hidden shadow-card-sm bg-[#1e1e1e] font-mono text-sm">
                <div className="bg-[#2d2d2d] px-4 py-2 border-b-2 border-black flex justify-between items-center text-white/50 text-xs font-black uppercase">
                  <span>api.ts</span>
                  <span>Git Merge Editor</span>
                </div>
                <div className="p-4 space-y-1">
                  <div className="text-white/50">{"function init() {"}</div>

                  {/* Conflict section */}
                  <div className="my-4 border-l-4 border-red-500 pl-2 bg-red-500/10 rounded-r">
                    <div className="flex gap-2 text-white items-center">
                      <button
                        onClick={() => handleResolve("current")}
                        className={`text-[10px] px-2 py-1 rounded-lg border-2 font-black transition-all hover:-translate-y-0.5 active:translate-y-0 ${resolvedStatus === "current" ? "bg-blue-500 border-black text-black shadow-card-sm" : "bg-transparent border-blue-400 text-blue-400 hover:bg-blue-400/20"}`}
                      >
                        Accept Current
                      </button>
                      <button
                        onClick={() => handleResolve("both")}
                        className={`text-[10px] px-2 py-1 rounded-lg border-2 font-black transition-all hover:-translate-y-0.5 active:translate-y-0 ${resolvedStatus === "both" ? "bg-purple-500 border-black text-black shadow-card-sm" : "bg-transparent border-purple-400 text-purple-400 hover:bg-purple-400/20"}`}
                      >
                        Accept Both
                      </button>
                    </div>

                    <div
                      className={`mt-2 p-2 font-bold ${resolvedStatus === "current" || resolvedStatus === "both" ? "text-blue-400 bg-blue-900/30" : "text-white/40"}`}
                    >
                      {"<<<<<<< HEAD (Current Change)"}
                      <br />
                      {"  const fetchUsers = () => api.get('/v2/users');"}
                    </div>

                    <div className="text-red-400 font-black py-1">
                      {"======="}
                    </div>

                    <div className="flex gap-2 text-white items-center mt-1">
                      <button
                        onClick={() => handleResolve("incoming")}
                        className={`text-[10px] px-2 py-1 rounded-lg border-2 font-black transition-all hover:-translate-y-0.5 active:translate-y-0 ${resolvedStatus === "incoming" ? "bg-green-500 border-black text-black shadow-card-sm" : "bg-transparent border-green-500 text-green-500 hover:bg-green-500/20"}`}
                      >
                        Accept Incoming
                      </button>
                    </div>

                    <div
                      className={`mt-2 p-2 font-bold ${resolvedStatus === "incoming" || resolvedStatus === "both" ? "text-green-400 bg-green-900/30" : "text-white/40"}`}
                    >
                      {
                        "  const fetchUsers = () => api.get('/v3/users', { timeout: 5000 });"
                      }
                      <br />
                      {">>>>>>> feature/api-v3 (Incoming Change)"}
                    </div>
                  </div>

                  <div className="text-white/50">{"}"}</div>
                </div>
              </div>

              {/* Action & Preview */}
              <div className="flex flex-col gap-4">
                <div className="flex-1 bg-surface-lowest border-4 border-black rounded-lg p-6 shadow-card-sm flex flex-col justify-center items-center text-center gap-4 dark:bg-[#151411] dark:border-[#2e2924]">
                  <h5 className="font-black">Preview Merged Output</h5>
                  {resolvedStatus === "unresolved" ? (
                    <div className="text-muted text-sm font-bold flex flex-col items-center gap-2">
                      <AlertTriangle size={32} className="text-yellow-500" />
                      Select a change to preview
                    </div>
                  ) : (
                    <div className="w-full text-left font-mono text-sm bg-[#1e1e1e] text-white p-4 rounded-lg border-4 border-black shadow-inner">
                      <div className="text-white/50">{"function init() {"}</div>
                      {(resolvedStatus === "current" ||
                        resolvedStatus === "both") && (
                        <div className="text-blue-400 font-bold pl-4">
                          {"const fetchUsers = () => api.get('/v2/users');"}
                        </div>
                      )}
                      {(resolvedStatus === "incoming" ||
                        resolvedStatus === "both") && (
                        <div className="text-green-400 font-bold pl-4">
                          {
                            "const fetchUsers = () => api.get('/v3/users', { timeout: 5000 });"
                          }
                        </div>
                      )}
                      <div className="text-white/50">{"}"}</div>
                    </div>
                  )}
                </div>

                <button
                  onClick={handleMerge}
                  disabled={resolvedStatus === "unresolved"}
                  className="w-full py-4 rounded-lg border-4 border-black font-black uppercase text-lg transition-all shadow-card-sm disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-1 active:translate-y-0 flex items-center justify-center gap-2 bg-primary text-black cursor-pointer"
                >
                  Complete Merge <ArrowRight size={20} />
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-green-100 border-4 border-green-600 rounded-2xl p-8 flex flex-col items-center justify-center text-center gap-4 animate-in fade-in zoom-in duration-500">
              <div className="w-20 h-20 bg-green-500 border-4 border-black rounded-full flex items-center justify-center shadow-card-sm mb-2 animate-bounce">
                <Check size={40} className="text-white" />
              </div>
              <h4 className="text-3xl font-black text-green-900 drop-shadow-sm">
                Conflict Resolved!
              </h4>
              <p className="text-green-800 font-bold max-w-md">
                You successfully evaluated the overlapping changes and merged
                the code. In a real repository, you would now commit this
                resolution.
              </p>
              <div className="mt-4 text-left font-mono text-sm bg-black text-white p-6 rounded-lg border-4 border-black w-full max-w-lg shadow-inner">
                <div className="text-green-400 font-black mb-2 border-b border-white/20 pb-2">
                  Output code:
                </div>
                <div className="text-white/50">{"function init() {"}</div>
                {(resolvedStatus === "current" ||
                  resolvedStatus === "both") && (
                  <div className="text-white font-bold pl-4">
                    {"const fetchUsers = () => api.get('/v2/users');"}
                  </div>
                )}
                {(resolvedStatus === "incoming" ||
                  resolvedStatus === "both") && (
                  <div className="text-white font-bold pl-4">
                    {
                      "const fetchUsers = () => api.get('/v3/users', { timeout: 5000 });"
                    }
                  </div>
                )}
                <div className="text-white/50">{"}"}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
