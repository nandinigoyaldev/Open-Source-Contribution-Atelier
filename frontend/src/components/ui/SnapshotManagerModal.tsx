import React, { useState, useEffect } from "react";
import {
  Camera,
  Clock,
  Check,
  Loader2,
  Trash2,
  X,
  Plus,
  GitFork,
  Globe,
} from "lucide-react";
import {
  WorkspaceSnapshot,
  fetchWorkspaceSnapshots,
  createWorkspaceSnapshot,
  restoreWorkspaceSnapshot,
  deleteWorkspaceSnapshot,
  updateWorkspaceSnapshot,
  forkWorkspaceSnapshot,
} from "../../lib/api";
import toast from "react-hot-toast";

interface SnapshotManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onRestoreComplete: () => void;
}

export function SnapshotManagerModal({
  isOpen,
  onClose,
  projectId,
  onRestoreComplete,
}: SnapshotManagerModalProps) {
  const [snapshots, setSnapshots] = useState<WorkspaceSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  const [newSnapshotName, setNewSnapshotName] = useState("");
  const [newSnapshotDesc, setNewSnapshotDesc] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => {
    if (isOpen && projectId) {
      loadSnapshots();
    }
  }, [isOpen, projectId]);

  const loadSnapshots = async () => {
    setLoading(true);
    try {
      const data = await fetchWorkspaceSnapshots();
      // Filter by projectId just in case the backend doesn't filter by project correctly for the user (it filters by user currently, so we might have multiple projects)
      const projectSnapshots = data.filter((s) => s.project === projectId);
      setSnapshots(projectSnapshots);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSnapshotName.trim() || !projectId) return;

    setCreating(true);
    try {
      const newSnapshot = await createWorkspaceSnapshot({
        project: projectId,
        name: newSnapshotName,
        description: newSnapshotDesc,
        metadata: {
          layout: "default", // placeholder for future
        },
      });
      setSnapshots([newSnapshot, ...snapshots]);
      setNewSnapshotName("");
      setNewSnapshotDesc("");
      setShowCreateForm(false);
      toast.success("Snapshot created successfully!");
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = async (id: string) => {
    if (
      !window.confirm(
        "Are you sure you want to restore this snapshot? All current unsaved changes will be lost.",
      )
    ) {
      return;
    }

    setRestoringId(id);
    try {
      await restoreWorkspaceSnapshot(id);
      toast.success("Workspace restored successfully!");
      onRestoreComplete();
      onClose();
    } catch (err) {
      console.error(err);
      toast.error("Failed to restore snapshot.");
    } finally {
      setRestoringId(null);
    }
  };

  const handleTogglePublic = async (snapshot: WorkspaceSnapshot) => {
    try {
      const updated = await updateWorkspaceSnapshot(snapshot.id, {
        is_public: !snapshot.is_public,
      });
      setSnapshots(
        snapshots.map((s) =>
          s.id === snapshot.id ? { ...s, is_public: updated.is_public } : s,
        ),
      );
      toast.success(
        updated.is_public
          ? "Snapshot is now public"
          : "Snapshot is now private",
      );
    } catch (err) {
      console.error(err);
      toast.error("Failed to update visibility");
    }
  };

  const handleFork = async (id: string) => {
    if (
      !window.confirm(
        "Are you sure you want to fork this snapshot into a new project?",
      )
    )
      return;
    try {
      await forkWorkspaceSnapshot(id);
      toast.success("Snapshot forked into a new project!");
    } catch (err) {
      console.error(err);
      toast.error("Failed to fork snapshot");
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this snapshot?"))
      return;
    try {
      await deleteWorkspaceSnapshot(id);
      setSnapshots(snapshots.filter((s) => s.id !== id));
      toast.success("Snapshot deleted");
    } catch (err) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#1a1a1a] rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden border border-gray-200 dark:border-gray-800 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-[#252525]">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg">
              <Camera className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                Workspace Snapshots
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Save and restore named restore points
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Create form or button */}
          {!showCreateForm ? (
            <button
              onClick={() => setShowCreateForm(true)}
              className="w-full flex items-center justify-center gap-2 py-4 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-xl text-gray-500 dark:text-gray-400 hover:border-blue-500 hover:text-blue-500 dark:hover:border-blue-400 dark:hover:text-blue-400 transition-colors"
            >
              <Plus className="w-5 h-5" />
              <span>Create New Snapshot</span>
            </button>
          ) : (
            <form
              onSubmit={handleCreate}
              className="bg-gray-50 dark:bg-[#222] p-4 rounded-xl border border-gray-200 dark:border-gray-700 space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Snapshot Name *
                </label>
                <input
                  type="text"
                  required
                  value={newSnapshotName}
                  onChange={(e) => setNewSnapshotName(e.target.value)}
                  placeholder="e.g. Before Refactoring API"
                  className="w-full px-3 py-2 bg-white dark:bg-[#151411] border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description (Optional)
                </label>
                <textarea
                  value={newSnapshotDesc}
                  onChange={(e) => setNewSnapshotDesc(e.target.value)}
                  placeholder="What's changing in this snapshot?"
                  className="w-full px-3 py-2 bg-white dark:bg-[#151411] border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none dark:text-white resize-none"
                  rows={2}
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newSnapshotName.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
                >
                  {creating && <Loader2 className="w-4 h-4 animate-spin" />}
                  Save Snapshot
                </button>
              </div>
            </form>
          )}

          {/* Timeline */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-gray-900 dark:text-gray-300 flex items-center gap-2">
              <Clock className="w-4 h-4" /> History
            </h3>

            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              </div>
            ) : snapshots.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400 border border-dashed border-gray-200 dark:border-gray-800 rounded-xl">
                No snapshots found for this workspace.
              </div>
            ) : (
              <div className="relative border-l-2 border-gray-200 dark:border-gray-800 ml-3 pl-6 space-y-6">
                {snapshots.map((snapshot) => (
                  <div key={snapshot.id} className="relative group">
                    {/* Timeline dot */}
                    <div className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full bg-white dark:bg-[#1a1a1a] border-2 border-blue-500" />

                    <div className="bg-white dark:bg-[#252525] p-4 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 transition-colors">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <h4 className="font-bold text-gray-900 dark:text-white">
                            {snapshot.name}
                          </h4>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {new Date(snapshot.created_at).toLocaleString()} •{" "}
                            {snapshot.files?.length || 0} files
                          </span>
                        </div>
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleDelete(snapshot.id)}
                            className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                            title="Delete Snapshot"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {snapshot.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                          {snapshot.description}
                        </p>
                      )}

                      <div className="mt-4 flex flex-wrap gap-2 justify-end">
                        <button
                          onClick={() => handleTogglePublic(snapshot)}
                          className={`flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${snapshot.is_public ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"}`}
                        >
                          <Globe className="w-4 h-4" />
                          {snapshot.is_public ? "Public" : "Private"}
                        </button>
                        <button
                          onClick={() => handleFork(snapshot.id)}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/40 rounded-lg transition-colors"
                        >
                          <GitFork className="w-4 h-4" />
                          Fork
                        </button>
                        <button
                          onClick={() => handleRestore(snapshot.id)}
                          disabled={restoringId !== null}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {restoringId === snapshot.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                          Restore Point
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
  );
}
