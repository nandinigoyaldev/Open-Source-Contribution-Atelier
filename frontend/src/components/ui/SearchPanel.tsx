import React, { useState, useEffect, useRef } from "react";
import { Search, Replace, CornerDownRight, Loader2 } from "lucide-react";
import { Project } from "../../lib/api";

interface SearchResult {
  file_id: string;
  path: string;
  matches: { line: number; content: string; start: number; end: number }[];
}

export function SearchPanel({
  project,
  onMatchClick,
}: {
  project: Project | null;
  onMatchClick: (fileId: string, line: number) => void;
}) {
  const [query, setQuery] = useState("");
  const [replaceWith, setReplaceWith] = useState("");
  const [isRegex, setIsRegex] = useState(false);
  const [matchCase, setMatchCase] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to sandbox websocket
    const wsUrl =
      import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws/sandbox/`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.action === "search_result") {
        setResults((prev) => {
          const newResults = [...prev];
          const existing = newResults.find((r) => r.file_id === data.file_id);
          if (existing) {
            existing.matches.push(...data.matches);
          } else {
            newResults.push({
              file_id: data.file_id,
              path: data.path,
              matches: data.matches,
            });
          }
          return newResults;
        });
      } else if (data.action === "search_done") {
        setIsSearching(false);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const handleSearch = () => {
    if (!project || !query) return;
    setResults([]);
    setIsSearching(true);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: "search_project",
          project_id: project.id,
          query,
          is_regex: isRegex,
          match_case: matchCase,
        }),
      );
    }
  };

  const totalMatches = results.reduce((acc, r) => acc + r.matches.length, 0);

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 border-r border-gray-800 text-sm overflow-hidden w-full">
      <div className="p-3 border-b border-gray-800 space-y-3">
        <h3 className="text-xs font-semibold uppercase text-gray-400 tracking-wider">
          Search
        </h3>

        <div className="relative flex items-center">
          <Search className="absolute left-2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search"
            className="w-full bg-[#252526] border border-[#3c3c3c] rounded px-8 py-1 focus:outline-none focus:border-blue-500"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <div className="absolute right-2 flex items-center gap-1">
            <button
              onClick={() => setMatchCase(!matchCase)}
              className={`p-0.5 rounded hover:bg-gray-700 ${matchCase ? "bg-gray-700 text-blue-400" : "text-gray-500"}`}
              title="Match Case (Aa)"
            >
              Aa
            </button>
            <button
              onClick={() => setIsRegex(!isRegex)}
              className={`p-0.5 rounded hover:bg-gray-700 ${isRegex ? "bg-gray-700 text-blue-400" : "text-gray-500"}`}
              title="Use Regular Expression (.*)"
            >
              .*
            </button>
          </div>
        </div>

        <div className="relative flex items-center">
          <Replace className="absolute left-2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Replace"
            className="w-full bg-[#252526] border border-[#3c3c3c] rounded px-8 py-1 focus:outline-none focus:border-blue-500"
            value={replaceWith}
            onChange={(e) => setReplaceWith(e.target.value)}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {isSearching && (
          <div className="flex items-center justify-center p-4 text-gray-500 gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Searching...
          </div>
        )}
        {!isSearching && results.length === 0 && query && (
          <div className="p-4 text-center text-gray-500">No results found</div>
        )}
        {!isSearching && results.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs text-gray-500 px-2 py-1">
              {totalMatches} results in {results.length} files
            </div>
            {results.map((r) => (
              <div key={r.file_id} className="mb-2">
                <div className="flex items-center gap-2 px-2 py-1 hover:bg-[#2a2d2e] cursor-pointer rounded bg-[#252526]">
                  <CornerDownRight className="w-3 h-3 text-gray-500" />
                  <span className="font-mono text-xs">{r.path}</span>
                  <span className="ml-auto text-xs bg-gray-700 px-1.5 rounded-full text-gray-400">
                    {r.matches.length}
                  </span>
                </div>
                <div>
                  {r.matches.map((m, idx) => (
                    <div
                      key={idx}
                      className="pl-6 pr-2 py-1 text-xs font-mono hover:bg-[#2a2d2e] cursor-pointer truncate"
                      onClick={() => onMatchClick(r.file_id, m.line)}
                    >
                      <span className="text-blue-400 mr-2">{m.line}</span>
                      <span>
                        {m.content.substring(0, m.start)}
                        <span className="bg-[#515c6a] text-white px-0.5 rounded">
                          {m.content.substring(m.start, m.end)}
                        </span>
                        {m.content.substring(m.end)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
