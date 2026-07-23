import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Project,
  ProjectFile,
  fetchProjects,
  createProject,
  createProjectFile,
  updateProjectFile,
  deleteProjectFile,
  exportWorkspaceZip,
  createCollabSession,
} from "../../lib/api";
import { ProjectExplorer } from "./ProjectExplorer";
import { CodeEditor } from "./CodeEditor";
import { SnippetLibraryModal } from "./SnippetLibraryModal";
import { SnapshotManagerModal } from "./SnapshotManagerModal";
import { Library, Camera, Download, Users } from "lucide-react";
import { SearchPanel } from "./SearchPanel";
import { TerminalWorkspace } from "./Terminal";

export function ProjectWorkspace() {
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isSnapshotManagerOpen, setIsSnapshotManagerOpen] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      let projects = await fetchProjects();
      if (projects.length === 0) {
        // Auto-create default project
        const defaultProject = await createProject("Default Project");
        await createProjectFile(
          defaultProject.id,
          "src/index.js",
          "// Welcome to your new project workspace!\n",
        );
        projects = [defaultProject];
      }

      const activeProject = projects[0];
      setProject(activeProject);

      // Fetch files for this project (though they might be returned nested in the project API, let's just use the nested array if present)
      if (activeProject.files) {
        setFiles(activeProject.files);
        if (activeProject.files.length > 0) {
          setActiveFileId(activeProject.files[0].id);
        } else {
          setActiveFileId(null);
        }
      }
    } catch (err) {
      console.error("Failed to load workspace", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load project on mount
  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const handleCreateFile = async (path: string) => {
    if (!project) return;
    try {
      const ext = path.split(".").pop() || "";
      let lang = "javascript";
      if (ext === "py") lang = "python";
      if (ext === "rs") lang = "rust";
      if (ext === "json") lang = "json";
      if (ext === "ts" || ext === "tsx") lang = "typescript";

      const newFile = await createProjectFile(project.id, path, "", lang);
      setFiles((prev) => [...prev, newFile]);
      setActiveFileId(newFile.id);
    } catch (err) {
      console.error("Failed to create file", err);
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await deleteProjectFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      if (activeFileId === fileId) {
        setActiveFileId(null);
      }
    } catch (err) {
      console.error("Failed to delete file", err);
    }
  };

  const activeFile = files.find((f) => f.id === activeFileId);

  // Debounced auto-save
  const handleCodeChange = useCallback(
    (newCode: string) => {
      if (!activeFileId) return;

      // Optimistic UI update
      setFiles((prev) =>
        prev.map((f) =>
          f.id === activeFileId ? { ...f, content: newCode } : f,
        ),
      );

      // Fire and forget API save
      updateProjectFile(activeFileId, { content: newCode }).catch((err) => {
        console.error("Failed to save file", err);
      });
    },
    [activeFileId],
  );

  const handleInsertSnippet = useCallback(
    (code: string) => {
      if (!activeFileId) return;
      setFiles((prev) =>
        prev.map((f) => {
          if (f.id === activeFileId) {
            const newContent =
              f.content + (f.content.endsWith("\n") ? "" : "\n") + code;
            updateProjectFile(activeFileId, { content: newContent }).catch(
              (err) => {
                console.error("Failed to save snippet insertion", err);
              },
            );
            return { ...f, content: newContent };
          }
          return f;
        }),
      );
    },
    [activeFileId],
  );

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        Loading Workspace...
      </div>
    );
  }

  return (
    <div className="flex h-full border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden bg-white dark:bg-[#1a1a1a]">
      <div
        id="tour-sandbox-explorer"
        className="h-full border-r border-gray-800"
      >
        <ProjectExplorer
          files={files}
          activeFileId={activeFileId}
          onSelectFile={setActiveFileId}
          onCreateFile={handleCreateFile}
          onDeleteFile={handleDeleteFile}
        />
      </div>
      <div
        id="tour-sandbox-search"
        className="w-[300px] border-r border-gray-800"
      >
        <SearchPanel
          project={project}
          onMatchClick={(fileId) => {
            setActiveFileId(fileId);
          }}
        />
      </div>

      <div className="flex-1 flex flex-col h-full bg-[#1e1e1e]">
        {activeFile ? (
          <>
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-[#252525]">
              <span className="text-sm text-gray-300 font-mono">
                {activeFile.path}
              </span>
              <div id="tour-sandbox-tools" className="flex items-center gap-2">
                <button
                  id="collab-start-btn"
                  onClick={async () => {
                    if (project) {
                      try {
                        const session = await createCollabSession(project.id);
                        navigate(`/collab/${session.id}`);
                      } catch (err) {
                        console.error("Failed to start collaboration", err);
                      }
                    }
                  }}
                  className="flex items-center gap-2 px-2 py-1 text-xs font-bold text-gray-300 border border-gray-600 rounded hover:bg-gray-700 transition-colors"
                >
                  <Users className="w-3.5 h-3.5 text-indigo-400" /> Start Collab
                </button>
                <button
                  onClick={async () => {
                    if (project) {
                      try {
                        await exportWorkspaceZip(project.id);
                      } catch (err) {
                        console.error("Failed to export workspace", err);
                      }
                    }
                  }}
                  className="flex items-center gap-2 px-2 py-1 text-xs font-bold text-gray-300 border border-gray-600 rounded hover:bg-gray-700 transition-colors"
                >
                  <Download className="w-3 h-3" /> Export
                </button>
                <button
                  onClick={() => setIsSnapshotManagerOpen(true)}
                  className="flex items-center gap-2 px-2 py-1 text-xs font-bold text-gray-300 border border-gray-600 rounded hover:bg-gray-700 transition-colors"
                >
                  <Camera className="w-3 h-3" /> Snapshots
                </button>
                <button
                  onClick={() => setIsLibraryOpen(true)}
                  className="flex items-center gap-2 px-2 py-1 text-xs font-bold text-gray-300 border border-gray-600 rounded hover:bg-gray-700 transition-colors"
                >
                  <Library className="w-3 h-3" /> Snippets
                </button>
              </div>
            </div>
            <div
              id="tour-sandbox-editor"
              className="flex-1 overflow-auto bg-[#151411]"
            >
              <CodeEditor
                code={activeFile.content}
                onChange={handleCodeChange}
                language={activeFile.language}
                minHeight="100%"
              />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a file to edit
          </div>
        )}
        <div
          id="tour-sandbox-terminal"
          className="h-1/3 min-h-[250px] max-h-[50%] flex flex-col border-t border-gray-800"
        >
          <TerminalWorkspace projectId={project?.id} />
        </div>
      </div>

      <SnippetLibraryModal
        isOpen={isLibraryOpen}
        onClose={() => setIsLibraryOpen(false)}
        onInsertCode={handleInsertSnippet}
      />

      {project && (
        <SnapshotManagerModal
          isOpen={isSnapshotManagerOpen}
          onClose={() => setIsSnapshotManagerOpen(false)}
          projectId={project.id}
          onRestoreComplete={loadWorkspace}
        />
      )}
    </div>
  );
}
