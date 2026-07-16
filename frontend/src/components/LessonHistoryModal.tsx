import React, { useEffect, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import { format } from "date-fns";
import { X, History } from "lucide-react";
import { fetchApi } from "../lib/api";

interface LessonVersion {
  id: number;
  content: string;
  summary: string;
  createdAt: string;
}

interface LessonHistoryModalProps {
  lessonId: number;
  currentContent: string;
  onClose: () => void;
}

export function LessonHistoryModal({
  lessonId,
  currentContent,
  onClose,
}: LessonHistoryModalProps) {
  const [versions, setVersions] = useState<LessonVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(
    null,
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    // Fetch versions from our new endpoint
    fetchApi(`/content/lessons/${lessonId}/versions/`)
      .then((res: { data: LessonVersion[] }) => {
        setVersions(res.data);
        if (res.data.length > 0) {
          setSelectedVersionId(res.data[0].id);
        }
      })
      .catch((err: unknown) => {
        console.error("Failed to load lesson versions", err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [lessonId]);

  const selectedVersion = versions.find((v) => v.id === selectedVersionId);
  const oldCode = selectedVersion ? selectedVersion.content : "";
  const newCode = currentContent;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-6">
      <div className="bg-background w-full max-w-6xl max-h-[90vh] rounded-xl border-2 border-border shadow-brutal flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b-2 border-border bg-accent/10 px-6 py-4">
          <div className="flex items-center gap-2">
            <History className="h-6 w-6 text-accent" />
            <h2 className="text-xl font-bold font-mono">
              Content Version History
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-black/5 dark:hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-64 border-r-2 border-border bg-card p-4 overflow-y-auto">
            <h3 className="font-bold text-sm text-muted-foreground mb-4 uppercase tracking-wider">
              Revisions
            </h3>
            {loading ? (
              <p className="text-sm">Loading versions...</p>
            ) : versions.length === 0 ? (
              <p className="text-sm italic">No previous versions found.</p>
            ) : (
              <div className="space-y-2">
                {versions.map((version) => (
                  <button
                    key={version.id}
                    onClick={() => setSelectedVersionId(version.id)}
                    className={`w-full text-left px-3 py-3 rounded-md border-2 text-sm transition-all ${
                      selectedVersionId === version.id
                        ? "border-accent bg-accent/10 font-bold"
                        : "border-transparent hover:border-border hover:bg-accent/5"
                    }`}
                  >
                    <div>
                      {format(new Date(version.createdAt), "MMM d, yyyy")}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {format(new Date(version.createdAt), "h:mm a")}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Diff Viewer */}
          <div className="flex-1 overflow-y-auto bg-white dark:bg-[#282c34]">
            {selectedVersionId ? (
              <ReactDiffViewer
                oldValue={oldCode}
                newValue={newCode}
                splitView={true}
                useDarkTheme={document.documentElement.classList.contains(
                  "dark",
                )}
                leftTitle="Selected Version"
                rightTitle="Current Content"
                styles={{
                  variables: {
                    dark: {
                      diffViewerBackground: "#282c34",
                      diffViewerColor: "#FFF",
                      addedBackground: "#044B53",
                      addedColor: "white",
                      removedBackground: "#632F34",
                      removedColor: "white",
                      wordAddedBackground: "#055d67",
                      wordRemovedBackground: "#7d383f",
                      addedGutterBackground: "#034148",
                      removedGutterBackground: "#632f34",
                      gutterBackground: "#2c313a",
                      gutterBackgroundDark: "#2c313a",
                      highlightBackground: "#2a3967",
                      highlightGutterBackground: "#2d4077",
                      emptyLineBackground: "#363946",
                    },
                  },
                }}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                Select a version to compare
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
