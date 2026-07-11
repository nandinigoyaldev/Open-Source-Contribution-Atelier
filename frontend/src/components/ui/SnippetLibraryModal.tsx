import React, { useState, useRef } from "react";
import { useSnippets } from "../../hooks/useSnippets";
import {
  X,
  BookOpen,
  Star,
  Folder,
  Plus,
  Search,
  Trash2,
  Download,
  Upload,
  Code2,
  Copy,
  ArrowRightSquare,
} from "lucide-react";
import toast from "react-hot-toast";

interface SnippetLibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInsertCode: (code: string) => void;
}

export function SnippetLibraryModal({
  isOpen,
  onClose,
  onInsertCode,
}: SnippetLibraryModalProps) {
  const {
    collections,
    snippets,
    isLoading,
    activeCollectionId,
    setActiveCollectionId,
    searchQuery,
    setSearchQuery,
    showFavoritesOnly,
    setShowFavoritesOnly,
    addCollection,
    removeCollection,
    addSnippet,
    removeSnippet,
    toggleFavorite,
    exportData,
    importData,
  } = useSnippets();

  const [isCreatingCollection, setIsCreatingCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");

  const [isCreatingSnippet, setIsCreatingSnippet] = useState(false);
  const [newSnippetData, setNewSnippetData] = useState({
    title: "",
    code: "",
    language: "python",
    description: "",
    tags: "",
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCollectionName.trim()) return;
    await addCollection(newCollectionName);
    setNewCollectionName("");
    setIsCreatingCollection(false);
  };

  const handleCreateSnippet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSnippetData.title.trim() || !newSnippetData.code.trim()) return;

    await addSnippet({
      title: newSnippetData.title,
      code: newSnippetData.code,
      language: newSnippetData.language,
      description: newSnippetData.description,
      tags: newSnippetData.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      collection: activeCollectionId || null,
    });

    setNewSnippetData({
      title: "",
      code: "",
      language: "python",
      description: "",
      tags: "",
    });
    setIsCreatingSnippet(false);
  };

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    toast.success("Copied to clipboard");
  };

  const handleInsert = (code: string) => {
    onInsertCode(code);
    onClose();
  };

  const handleFileImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      importData(file);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#151411] w-full max-w-6xl h-[85vh] rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#1f1c18]">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <BookOpen className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-black text-gray-900 dark:text-white">
                Snippet Library
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">
                Save and reuse your code
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept=".json"
              onChange={handleFileImport}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-gray-100 dark:hover:bg-[#2e2924] transition-colors"
            >
              <Upload className="w-4 h-4" /> Import
            </button>
            <button
              onClick={exportData}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-gray-100 dark:hover:bg-[#2e2924] transition-colors"
            >
              <Download className="w-4 h-4" /> Export
            </button>
            <button
              onClick={onClose}
              className="p-2 ml-2 hover:bg-gray-100 dark:hover:bg-[#2e2924] rounded-lg transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-64 border-r-4 border-black dark:border-[#2e2924] bg-gray-50 dark:bg-[#1a1816] flex flex-col">
            <div className="p-4 space-y-2 flex-1 overflow-y-auto">
              <button
                onClick={() => {
                  setActiveCollectionId(null);
                  setShowFavoritesOnly(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl font-bold text-sm transition-all border-2 ${
                  !activeCollectionId && !showFavoritesOnly
                    ? "bg-black text-white border-black dark:bg-white dark:text-black dark:border-white"
                    : "border-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-[#2e2924]"
                }`}
              >
                <Code2 className="w-4 h-4" /> All Snippets
              </button>

              <button
                onClick={() => {
                  setActiveCollectionId(null);
                  setShowFavoritesOnly(true);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl font-bold text-sm transition-all border-2 ${
                  showFavoritesOnly
                    ? "bg-yellow-400 text-black border-black"
                    : "border-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-[#2e2924]"
                }`}
              >
                <Star className="w-4 h-4" /> Favorites
              </button>

              <div className="pt-6 pb-2">
                <div className="flex items-center justify-between px-2 mb-2">
                  <span className="text-xs font-black text-gray-400 uppercase tracking-wider">
                    Collections
                  </span>
                  <button
                    onClick={() => setIsCreatingCollection(true)}
                    className="text-gray-400 hover:text-black dark:hover:text-white transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>

                {isCreatingCollection && (
                  <form onSubmit={handleCreateCollection} className="mb-2">
                    <input
                      autoFocus
                      type="text"
                      placeholder="Name..."
                      className="w-full px-3 py-1.5 text-sm rounded-lg border-2 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] outline-none"
                      value={newCollectionName}
                      onChange={(e) => setNewCollectionName(e.target.value)}
                      onBlur={() => {
                        if (!newCollectionName) setIsCreatingCollection(false);
                      }}
                    />
                  </form>
                )}

                {collections.map((c) => (
                  <div key={c.id} className="group flex items-center gap-2">
                    <button
                      onClick={() => {
                        setActiveCollectionId(c.id);
                        setShowFavoritesOnly(false);
                      }}
                      className={`flex-1 flex items-center gap-3 px-3 py-2 rounded-xl font-bold text-sm transition-all border-2 ${
                        activeCollectionId === c.id
                          ? "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-900/50"
                          : "border-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-[#2e2924]"
                      }`}
                    >
                      <Folder className="w-4 h-4" />
                      <span className="truncate">{c.name}</span>
                    </button>
                    <button
                      onClick={() => removeCollection(c.id)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Main Area */}
          <div className="flex-1 flex flex-col bg-white dark:bg-[#151411]">
            <div className="p-4 border-b-2 border-gray-100 dark:border-[#1f1c18] flex items-center justify-between gap-4">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search snippets..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 rounded-xl border-2 border-black dark:border-[#2e2924] bg-gray-50 dark:bg-[#1a1816] outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <button
                onClick={() => setIsCreatingSnippet(!isCreatingSnippet)}
                className="flex items-center gap-2 px-4 py-2 bg-black text-white dark:bg-white dark:text-black font-bold rounded-xl hover:brightness-110 transition-all border-2 border-transparent"
              >
                <Plus className="w-5 h-5" /> New Snippet
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-[#1a1816]">
              {isCreatingSnippet && (
                <form
                  onSubmit={handleCreateSnippet}
                  className="mb-6 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-2xl p-4 shadow-sm animate-in slide-in-from-top-4"
                >
                  <h3 className="font-black text-lg mb-4">
                    Create New Snippet
                  </h3>
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <input
                        type="text"
                        placeholder="Snippet Title"
                        required
                        className="flex-1 px-4 py-2 border-2 border-black dark:border-[#2e2924] rounded-xl outline-none bg-transparent"
                        value={newSnippetData.title}
                        onChange={(e) =>
                          setNewSnippetData((p) => ({
                            ...p,
                            title: e.target.value,
                          }))
                        }
                      />
                      <select
                        className="px-4 py-2 border-2 border-black dark:border-[#2e2924] rounded-xl outline-none bg-transparent font-bold"
                        value={newSnippetData.language}
                        onChange={(e) =>
                          setNewSnippetData((p) => ({
                            ...p,
                            language: e.target.value,
                          }))
                        }
                      >
                        <option value="python">Python</option>
                        <option value="javascript">JavaScript</option>
                        <option value="typescript">TypeScript</option>
                        <option value="html">HTML</option>
                        <option value="css">CSS</option>
                        <option value="json">JSON</option>
                      </select>
                    </div>
                    <textarea
                      placeholder="Paste your code here..."
                      required
                      className="w-full h-40 px-4 py-3 border-2 border-black dark:border-[#2e2924] rounded-xl outline-none bg-gray-50 dark:bg-[#151411] font-mono text-sm resize-none"
                      value={newSnippetData.code}
                      onChange={(e) =>
                        setNewSnippetData((p) => ({
                          ...p,
                          code: e.target.value,
                        }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Tags (comma separated, optional)"
                      className="w-full px-4 py-2 border-2 border-black dark:border-[#2e2924] rounded-xl outline-none bg-transparent"
                      value={newSnippetData.tags}
                      onChange={(e) =>
                        setNewSnippetData((p) => ({
                          ...p,
                          tags: e.target.value,
                        }))
                      }
                    />
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setIsCreatingSnippet(false)}
                        className="px-4 py-2 font-bold hover:bg-gray-100 dark:hover:bg-[#2e2924] rounded-xl transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-6 py-2 bg-black text-white dark:bg-white dark:text-black font-bold rounded-xl hover:brightness-110 transition-all border-2 border-black"
                      >
                        Save Snippet
                      </button>
                    </div>
                  </div>
                </form>
              )}

              {isLoading ? (
                <div className="flex justify-center items-center h-full text-gray-500">
                  Loading snippets...
                </div>
              ) : snippets.length === 0 && !isCreatingSnippet ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                  <div className="p-4 bg-gray-200 dark:bg-[#2e2924] rounded-full">
                    <Code2 className="w-8 h-8 text-gray-400" />
                  </div>
                  <p className="font-bold">No snippets found.</p>
                  <button
                    onClick={() => setIsCreatingSnippet(true)}
                    className="text-blue-500 hover:underline"
                  >
                    Create your first snippet
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {snippets.map((snippet) => (
                    <div
                      key={snippet.id}
                      className="bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden hover:-translate-y-1 hover:shadow-lg transition-all duration-200 group"
                    >
                      <div className="p-4 border-b-2 border-gray-100 dark:border-[#2e2924] flex items-start justify-between gap-4">
                        <div>
                          <h3 className="font-black text-lg text-gray-900 dark:text-white mb-1">
                            {snippet.title}
                          </h3>
                          <div className="flex flex-wrap gap-2">
                            <span className="px-2 py-0.5 bg-gray-100 dark:bg-[#2e2924] text-xs font-bold rounded-md uppercase tracking-wider">
                              {snippet.language}
                            </span>
                            {snippet.tags.map((t) => (
                              <span
                                key={t}
                                className="px-2 py-0.5 bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 text-xs font-bold rounded-md"
                              >
                                #{t}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => toggleFavorite(snippet)}
                            className={`p-2 rounded-lg transition-colors ${snippet.is_favorite ? "text-yellow-400 hover:bg-yellow-50 dark:hover:bg-yellow-900/20" : "text-gray-400 hover:bg-gray-100 dark:hover:bg-[#2e2924]"}`}
                          >
                            <Star
                              className="w-5 h-5"
                              fill={
                                snippet.is_favorite ? "currentColor" : "none"
                              }
                            />
                          </button>
                          <button
                            onClick={() => removeSnippet(snippet.id)}
                            className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        </div>
                      </div>

                      <div className="bg-[#1e1e1e] p-4 text-sm font-mono text-gray-300 overflow-x-auto relative group/code">
                        <pre className="m-0">
                          <code>{snippet.code}</code>
                        </pre>

                        <div className="absolute top-2 right-2 flex items-center gap-2 opacity-0 group-hover/code:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleCopy(snippet.code)}
                            className="p-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors shadow-lg"
                            title="Copy to Clipboard"
                          >
                            <Copy className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleInsert(snippet.code)}
                            className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors shadow-lg flex items-center gap-2 font-bold"
                            title="Insert into Editor"
                          >
                            <ArrowRightSquare className="w-4 h-4" /> Insert
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
