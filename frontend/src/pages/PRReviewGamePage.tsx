import React, { useState } from "react";
import { CodeDiffViewer } from "../components/ui/CodeDiffViewer";
import { Check, X, MessageSquare, Trophy } from "lucide-react";
import toast from "react-hot-toast";

const LEVELS = [
  {
    id: 1,
    title: "Level 1: The Infinite Loop",
    description:
      "Review this pull request and find the bug. Should you approve, request changes, or comment?",
    originalCode: `function countDown(start) {\n  let current = start;\n  while (current > 0) {\n    console.log(current);\n    current--;\n  }\n}`,
    modifiedCode: `function countDown(start) {\n  let current = start;\n  while (current > 0) {\n    console.log(current);\n    // bug introduced here\n    current++;\n  }\n}`,
    correctAction: "request_changes",
    feedback:
      "Good catch! The developer changed `current--` to `current++`, creating an infinite loop.",
  },
  {
    id: 2,
    title: "Level 2: The Console Log",
    description: "Review this pull request. Is it ready to be merged?",
    originalCode: `function calculateTotal(items) {\n  return items.reduce((sum, item) => sum + item.price, 0);\n}`,
    modifiedCode: `function calculateTotal(items) {\n  const total = items.reduce((sum, item) => sum + item.price, 0);\n  console.log("Total is:", total);\n  return total;\n}`,
    correctAction: "comment",
    feedback:
      "Nice! Leaving a comment is best here. It's not necessarily broken, but we usually shouldn't merge console.logs into production.",
  },
  {
    id: 3,
    title: "Level 3: The Optimization",
    description: "The author optimized the sorting algorithm. Review the PR.",
    originalCode: `function sortUsers(users) {\n  return users.sort((a, b) => {\n    if (a.name < b.name) return -1;\n    if (a.name > b.name) return 1;\n    return 0;\n  });\n}`,
    modifiedCode: `function sortUsers(users) {\n  return users.sort((a, b) => a.name.localeCompare(b.name));\n}`,
    correctAction: "approve",
    feedback:
      "Perfect! You approved a great optimization that uses built-in localeCompare.",
  },
];

export function PRReviewGamePage() {
  const [currentLevel, setCurrentLevel] = useState(0);
  const [score, setScore] = useState(0);
  const [gameOver, setGameOver] = useState(false);

  const handleAction = (action: "approve" | "request_changes" | "comment") => {
    const level = LEVELS[currentLevel];

    if (action === level.correctAction) {
      toast.success(level.feedback, { duration: 4000 });
      setScore(score + 100);
    } else {
      toast.error(
        `Not quite! The best action was to ${level.correctAction.replace("_", " ")}.`,
        { duration: 4000 },
      );
    }

    if (currentLevel < LEVELS.length - 1) {
      setCurrentLevel(currentLevel + 1);
    } else {
      setGameOver(true);
    }
  };

  const resetGame = () => {
    setCurrentLevel(0);
    setScore(0);
    setGameOver(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 flex flex-col min-h-[calc(100vh-64px)]">
      <div>
        <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
          <span>🕵️</span> PR Reviewer Sandbox
        </h1>
        <p className="mt-2 text-muted dark:text-[#c4bbae]">
          Test your code review skills. Analyze the diffs and choose the right
          action!
        </p>
      </div>

      <div className="flex items-center justify-between bg-surface-low border-2 border-black rounded-xl p-4 dark:bg-[#151411] dark:border-[#2e2924]">
        <span className="font-bold text-lg dark:text-[#f0ebe2]">
          Score: <span className="text-primary">{score}</span>
        </span>
        {!gameOver && (
          <span className="font-bold text-lg dark:text-[#f0ebe2]">
            Level {currentLevel + 1} of {LEVELS.length}
          </span>
        )}
      </div>

      {!gameOver ? (
        <div className="flex-1 flex flex-col gap-6">
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card">
            <h2 className="text-xl font-black mb-2 dark:text-[#f0ebe2]">
              {LEVELS[currentLevel].title}
            </h2>
            <p className="text-muted dark:text-[#c4bbae] mb-6">
              {LEVELS[currentLevel].description}
            </p>

            <CodeDiffViewer
              originalCode={LEVELS[currentLevel].originalCode}
              modifiedCode={LEVELS[currentLevel].modifiedCode}
              fileName={`challenge_${LEVELS[currentLevel].id}.js`}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => handleAction("approve")}
              className="flex flex-col items-center gap-2 p-4 bg-green-100 hover:bg-green-200 border-2 border-black rounded-xl shadow-card hover:-translate-y-1 transition-all"
            >
              <Check className="text-green-700" size={32} />
              <span className="font-black text-green-900">Approve</span>
              <span className="text-xs text-green-800 text-center">
                Looks good to me! Merge it.
              </span>
            </button>

            <button
              onClick={() => handleAction("comment")}
              className="flex flex-col items-center gap-2 p-4 bg-blue-100 hover:bg-blue-200 border-2 border-black rounded-xl shadow-card hover:-translate-y-1 transition-all"
            >
              <MessageSquare className="text-blue-700" size={32} />
              <span className="font-black text-blue-900">Comment</span>
              <span className="text-xs text-blue-800 text-center">
                Leave feedback without blocking.
              </span>
            </button>

            <button
              onClick={() => handleAction("request_changes")}
              className="flex flex-col items-center gap-2 p-4 bg-red-100 hover:bg-red-200 border-2 border-black rounded-xl shadow-card hover:-translate-y-1 transition-all"
            >
              <X className="text-red-700" size={32} />
              <span className="font-black text-red-900">Request Changes</span>
              <span className="text-xs text-red-800 text-center">
                Found a bug! Block merge.
              </span>
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl p-12 shadow-card text-center gap-6">
          <Trophy className="text-accent w-24 h-24 mb-4" />
          <h2 className="text-4xl font-black dark:text-[#f0ebe2]">
            Game Over!
          </h2>
          <p className="text-xl text-muted dark:text-[#c4bbae]">
            Your final review score is{" "}
            <span className="text-primary font-black">{score}</span> /{" "}
            {LEVELS.length * 100}
          </p>
          <button
            onClick={resetGame}
            className="mt-6 px-8 py-3 bg-primary text-black font-black text-lg border-4 border-black rounded-xl hover:-translate-y-1 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all"
          >
            Play Again
          </button>
        </div>
      )}
    </div>
  );
}
