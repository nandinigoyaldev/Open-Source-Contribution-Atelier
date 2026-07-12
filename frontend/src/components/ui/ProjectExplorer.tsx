import React, { useState, useMemo } from "react";
import {
  Folder,
  File as FileIcon,
  ChevronRight,
  ChevronDown,
  Plus,
  Trash2,
  FileCode2,
  FileJson,
  FileType2,
} from "lucide-react";
import { ProjectFile } from "../../lib/api";

interface ProjectExplorerProps {
  files: ProjectFile[];
  activeFileId: string | null;
  onSelectFile: (fileId: string) => void;
  onCreateFile: (path: string) => void;
  onDeleteFile: (fileId: string) => void;
}

// Helper to build a nested tree from flat paths
type TreeNode = {
  name: string;
  path: string;
  type: "file" | "folder";
  file?: ProjectFile;
  children: { [key: string]: TreeNode };
};

function buildTree(files: ProjectFile[]): TreeNode {
  const root: TreeNode = {
    name: "root",
    path: "",
    type: "folder",
    children: {},
  };

  files.forEach((file) => {
    const parts = file.path.split("/");
    let current = root;

    parts.forEach((part, index) => {
      if (index === parts.length - 1) {
        // It's a file
        current.children[part] = {
          name: part,
          path: file.path,
          type: "file",
          file: file,
          children: {},
        };
      } else {
        // It's a folder
        if (!current.children[part]) {
          const folderPath = parts.slice(0, index + 1).join("/");
          current.children[part] = {
            name: part,
            path: folderPath,
            type: "folder",
            children: {},
          };
        }
        current = current.children[part];
      }
    });
  });

  return root;
}

function getFileIcon(name: string) {
  if (name.endsWith(".ts") || name.endsWith(".tsx"))
    return <FileType2 size={16} className="text-blue-400" />;
  if (name.endsWith(".json"))
    return <FileJson size={16} className="text-yellow-400" />;
  if (name.endsWith(".js") || name.endsWith(".jsx"))
    return <FileCode2 size={16} className="text-yellow-300" />;
  return <FileIcon size={16} className="text-gray-400" />;
}

export function ProjectExplorer({
  files,
  activeFileId,
  onSelectFile,
  onCreateFile,
  onDeleteFile,
}: ProjectExplorerProps) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(
    new Set([""]),
  );
  const [isCreating, setIsCreating] = useState<{ parentPath: string } | null>(
    null,
  );
  const [newFileName, setNewFileName] = useState("");

  const tree = useMemo(() => buildTree(files), [files]);

  const toggleFolder = (path: string) => {
    const next = new Set(expandedFolders);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setExpandedFolders(next);
  };

  const handleCreateSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && newFileName.trim()) {
      const fullPath = isCreating?.parentPath
        ? `${isCreating.parentPath}/${newFileName.trim()}`
        : newFileName.trim();
      onCreateFile(fullPath);
      setIsCreating(null);
      setNewFileName("");
    } else if (e.key === "Escape") {
      setIsCreating(null);
      setNewFileName("");
    }
  };

  const renderNode = (node: TreeNode, depth: number = 0) => {
    const isExpanded = expandedFolders.has(node.path);
    const isActive = node.type === "file" && node.file?.id === activeFileId;
    const paddingLeft = `${depth * 12 + 8}px`;

    return (
      <div key={node.path}>
        <div
          className={`flex items-center group cursor-pointer py-1 pr-2 hover:bg-gray-800 transition-colors ${isActive ? "bg-gray-800 text-white" : "text-gray-400"}`}
          style={{ paddingLeft }}
          onClick={() => {
            if (node.type === "folder") toggleFolder(node.path);
            else if (node.file) onSelectFile(node.file.id);
          }}
        >
          {node.type === "folder" ? (
            <span className="mr-1">
              {isExpanded ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
            </span>
          ) : (
            <span className="mr-1 w-[14px]"></span>
          )}

          <span className="mr-2">
            {node.type === "folder" ? (
              <Folder size={16} className="text-blue-400" />
            ) : (
              getFileIcon(node.name)
            )}
          </span>

          <span className="flex-1 truncate text-sm select-none">
            {node.name}
          </span>

          {node.type === "file" && node.file && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteFile(node.file!.id);
              }}
              className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity p-1"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>

        {node.type === "folder" && isExpanded && (
          <div>
            {Object.values(node.children)
              .sort((a, b) => {
                // Folders first
                if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
                return a.name.localeCompare(b.name);
              })
              .map((child) => renderNode(child, depth + 1))}

            {isCreating?.parentPath ===
              (node.path === "root" ? "" : node.path) && (
              <div
                className="flex items-center py-1 pr-2"
                style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
              >
                <FileIcon size={16} className="text-gray-400 mr-2" />
                <input
                  autoFocus
                  className="bg-gray-900 text-white text-sm w-full outline-none px-1 rounded border border-gray-700 focus:border-blue-500"
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  onKeyDown={handleCreateSubmit}
                  onBlur={() => {
                    setIsCreating(null);
                    setNewFileName("");
                  }}
                  placeholder="filename.js"
                />
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] border-r border-gray-800 text-gray-300 w-64 flex-shrink-0">
      <div className="flex items-center justify-between p-3 border-b border-gray-800">
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
          Project Files
        </h3>
        <button
          onClick={() => {
            setExpandedFolders((prev) => new Set(prev).add(""));
            setIsCreating({ parentPath: "" });
          }}
          className="hover:text-white transition-colors p-1"
          title="New File"
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {Object.keys(tree.children).length === 0 && !isCreating ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500">
            No files in project. Click + to add one.
          </div>
        ) : (
          <>
            {Object.values(tree.children)
              .sort((a, b) => {
                if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
                return a.name.localeCompare(b.name);
              })
              .map((child) => renderNode(child, 0))}

            {isCreating?.parentPath === "" && (
              <div className="flex items-center py-1 px-2">
                <FileIcon size={16} className="text-gray-400 mr-2 ml-[14px]" />
                <input
                  autoFocus
                  className="bg-gray-900 text-white text-sm w-full outline-none px-1 rounded border border-gray-700 focus:border-blue-500"
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  onKeyDown={handleCreateSubmit}
                  onBlur={() => {
                    setIsCreating(null);
                    setNewFileName("");
                  }}
                  placeholder="filename.js"
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
