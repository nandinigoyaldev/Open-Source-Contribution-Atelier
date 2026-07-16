import React, { useState, useMemo } from "react";
import { X, Search, Copy, Check } from "lucide-react";

interface GitCommand {
  category: string;
  name: string;
  command: string;
  description: string;
  example?: string;
}

const GIT_COMMANDS: GitCommand[] = [
  // Getting Started
  {
    category: "Getting Started",
    name: "Initialize Repository",
    command: "git init",
    description: "Create a new Git repository in the current directory",
    example: "git init",
  },
  {
    category: "Getting Started",
    name: "Clone Repository",
    command: "git clone <url>",
    description: "Clone a remote repository to your local machine",
    example: "git clone https://github.com/user/repo.git",
  },
  {
    category: "Getting Started",
    name: "Check Status",
    command: "git status",
    description:
      "Show the working tree status (modified, staged, untracked files)",
  },

  // Basic Snapshotting
  {
    category: "Snapshotting",
    name: "Stage File(s)",
    command: "git add <file>",
    description: "Add file changes to the staging area",
    example: "git add index.html\ngit add .",
  },
  {
    category: "Snapshotting",
    name: "Stage All Changes",
    command: "git add -A",
    description: "Stage all changes including deletions",
  },
  {
    category: "Snapshotting",
    name: "Commit Changes",
    command: "git commit -m 'message'",
    description: "Commit staged changes with a descriptive message",
    example: "git commit -m 'Add login feature'",
  },
  {
    category: "Snapshotting",
    name: "Amend Commit",
    command: "git commit --amend",
    description:
      "Modify the most recent commit (add forgotten files or edit message)",
    example: "git commit --amend --no-edit",
  },
  {
    category: "Snapshotting",
    name: "View Changes",
    command: "git diff",
    description:
      "Show unstaged changes between working directory and staging area",
  },
  {
    category: "Snapshotting",
    name: "View Staged Changes",
    command: "git diff --staged",
    description: "Show staged changes that will be committed",
  },

  // Branching & Merging
  {
    category: "Branching",
    name: "List Branches",
    command: "git branch",
    description: "List all local branches",
    example: "git branch -a  (all including remote)",
  },
  {
    category: "Branching",
    name: "Create Branch",
    command: "git branch <name>",
    description: "Create a new branch",
    example: "git branch feature/login",
  },
  {
    category: "Branching",
    name: "Switch Branch",
    command: "git checkout <branch>",
    description: "Switch to a different branch",
    example: "git checkout main\ngit checkout -b new-branch  (create & switch)",
  },
  {
    category: "Branching",
    name: "Delete Branch",
    command: "git branch -d <branch>",
    description: "Delete a local branch",
    example: "git branch -d feature/old",
  },
  {
    category: "Branching",
    name: "Merge Branch",
    command: "git merge <branch>",
    description: "Merge a branch into the current branch",
    example: "git merge feature/login",
  },
  {
    category: "Branching",
    name: "Abort Merge",
    command: "git merge --abort",
    description: "Cancel an ongoing merge and return to pre-merge state",
  },

  // Remote Operations
  {
    category: "Remote",
    name: "Fetch Updates",
    command: "git fetch",
    description: "Download commits, files, and refs from a remote repository",
  },
  {
    category: "Remote",
    name: "Pull Changes",
    command: "git pull",
    description: "Fetch and merge changes from remote to current branch",
    example: "git pull origin main",
  },
  {
    category: "Remote",
    name: "Push Changes",
    command: "git push",
    description: "Upload local branch commits to remote repository",
    example: "git push -u origin feature  (set upstream)",
  },
  {
    category: "Remote",
    name: "Push to Remote",
    command: "git push <remote> <branch>",
    description: "Push a specific branch to a remote",
    example: "git push origin main",
  },
  {
    category: "Remote",
    name: "Set Remote URL",
    command: "git remote set-url origin <url>",
    description: "Change the URL of a remote",
    example: "git remote set-url origin https://github.com/user/repo.git",
  },

  // Rebasing
  {
    category: "Rebasing",
    name: "Start Rebase",
    command: "git rebase <branch>",
    description: "Reapply commits on top of another branch",
    example: "git rebase main",
  },
  {
    category: "Rebasing",
    name: "Continue Rebase",
    command: "git rebase --continue",
    description: "Continue rebase after resolving conflicts",
  },
  {
    category: "Rebasing",
    name: "Abort Rebase",
    command: "git rebase --abort",
    description: "Cancel rebase and return to original branch state",
  },
  {
    category: "Rebasing",
    name: "Interactive Rebase",
    command: "git rebase -i <commit>",
    description: "Interactive rebase to edit, reorder, or squash commits",
    example: "git rebase -i HEAD~3",
  },

  // Undoing Changes
  {
    category: "Undo",
    name: "Unstage File",
    command: "git reset HEAD <file>",
    description: "Unstage a file while preserving changes",
    example: "git reset HEAD index.html",
  },
  {
    category: "Undo",
    name: "Discard Changes",
    command: "git checkout -- <file>",
    description: "Discard local changes to a file",
    example: "git checkout -- index.html",
  },
  {
    category: "Undo",
    name: "Reset to Commit",
    command: "git reset --hard <commit>",
    description: "Reset to a specific commit, discarding all changes",
    example: "git reset --hard HEAD~1",
  },
  {
    category: "Undo",
    name: "Revert Commit",
    command: "git revert <commit>",
    description: "Create a new commit that undoes a previous commit",
    example: "git revert abc1234",
  },

  // Viewing History
  {
    category: "History",
    name: "View Log",
    command: "git log",
    description: "Show commit history",
    example: "git log --oneline --graph",
  },
  {
    category: "History",
    name: "View Recent Commits",
    command: "git log -n <count>",
    description: "Show the last n commits",
    example: "git log -5",
  },
  {
    category: "History",
    name: "Show Commit Details",
    command: "git show <commit>",
    description: "Show details of a specific commit",
    example: "git show abc1234",
  },

  // Stashing
  {
    category: "Stashing",
    name: "Create Stash",
    command: "git stash",
    description: "Temporarily save uncommitted changes",
  },
  {
    category: "Stashing",
    name: "List Stashes",
    command: "git stash list",
    description: "Show all stashed changes",
  },
  {
    category: "Stashing",
    name: "Apply Stash",
    command: "git stash pop",
    description: "Apply and remove the most recent stash",
    example: "git stash apply  (keep stash)",
  },

  // Advanced
  {
    category: "Advanced",
    name: "Interactive Add",
    command: "git add -p",
    description: "Interactively stage patches (portions of files)",
  },
  {
    category: "Advanced",
    name: "Clean Untracked",
    command: "git clean -fd",
    description: "Remove untracked files and directories",
    example: "git clean -n  (preview first)",
  },
  {
    category: "Advanced",
    name: "Tag Commit",
    command: "git tag <name>",
    description: "Create a tag for a specific commit",
    example: "git tag v1.0.0",
  },
  {
    category: "Advanced",
    name: "Bisect",
    command: "git bisect start",
    description: "Use binary search to find the commit that introduced a bug",
    example: "git bisect start\ngit bisect bad\ngit bisect good abc123",
  },
];

interface GitCheatSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onInsertCommand?: (command: string) => void;
}

export function GitCheatSheet({
  isOpen,
  onClose,
  onInsertCommand,
}: GitCheatSheetProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);

  const categories = useMemo(() => {
    return [...new Set(GIT_COMMANDS.map((cmd) => cmd.category))];
  }, []);

  const filteredCommands = useMemo(() => {
    let commands = GIT_COMMANDS;

    if (selectedCategory) {
      commands = commands.filter((cmd) => cmd.category === selectedCategory);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      commands = commands.filter(
        (cmd) =>
          cmd.name.toLowerCase().includes(query) ||
          cmd.command.toLowerCase().includes(query) ||
          cmd.description.toLowerCase().includes(query) ||
          cmd.category.toLowerCase().includes(query),
      );
    }

    return commands;
  }, [searchQuery, selectedCategory]);

  const handleCopy = async (command: string) => {
    await navigator.clipboard.writeText(command);
    setCopiedCommand(command);
    setTimeout(() => setCopiedCommand(null), 2000);
  };

  const handleInsert = (command: string) => {
    if (onInsertCommand) {
      onInsertCommand(command);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-4xl max-h-[85vh] mx-4 bg-[#1a1a2e] rounded-xl shadow-2xl border border-gray-700 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div>
            <h2 className="text-xl font-bold text-white">Git Cheat Sheet</h2>
            <p className="text-sm text-gray-400 mt-1">
              Quick reference for common Git commands
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-gray-700"
          >
            <X size={20} />
          </button>
        </div>

        {/* Search & Filters */}
        <div className="px-6 py-4 border-b border-gray-700 space-y-3">
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
              size={18}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search commands..."
              className="w-full pl-10 pr-4 py-2.5 bg-[#0f0f1d] border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                selectedCategory === null
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              All
            </button>
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                  selectedCategory === category
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>

        {/* Commands List */}
        <div className="flex-1 overflow-y-auto p-6">
          {filteredCommands.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <Search className="mx-auto mb-3 opacity-50" size={40} />
              <p>No commands found matching "{searchQuery}"</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCommands.map((cmd, index) => (
                <div
                  key={`${cmd.category}-${cmd.name}-${index}`}
                  className="bg-[#0f0f1d] rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded">
                          {cmd.category}
                        </span>
                        <h4 className="text-white font-medium">{cmd.name}</h4>
                      </div>
                      <p className="text-sm text-gray-400 mb-2">
                        {cmd.description}
                      </p>
                      <div className="flex items-center gap-2">
                        <code className="text-sm bg-gray-800 text-green-400 px-3 py-1.5 rounded font-mono">
                          {cmd.command}
                        </code>
                      </div>
                      {cmd.example && (
                        <p className="text-xs text-gray-500 mt-1 font-mono">
                          e.g., {cmd.example}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleCopy(cmd.command)}
                        className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
                        title="Copy command"
                      >
                        {copiedCommand === cmd.command ? (
                          <Check size={16} className="text-green-400" />
                        ) : (
                          <Copy size={16} />
                        )}
                      </button>
                      {onInsertCommand && (
                        <button
                          onClick={() => handleInsert(cmd.command)}
                          className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                        >
                          Use
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-700 bg-[#0f0f1d]">
          <p className="text-xs text-gray-500 text-center">
            Press{" "}
            <kbd className="px-1.5 py-0.5 bg-gray-700 rounded text-gray-300">
              Esc
            </kbd>{" "}
            to close
          </p>
        </div>
      </div>
    </div>
  );
}
