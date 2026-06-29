import React, { useState, useEffect } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/themes/prism-tomorrow.css"; // Dark theme
import { Play, RotateCcw, CheckCircle2, XCircle } from "lucide-react";
import { usePythonSandbox } from "../../hooks/usePythonSandbox";
import { PythonExercise } from "../../lib/lessons";

interface PythonSandboxProps {
  exercise: PythonExercise;
  onSuccess: () => void;
}

export function PythonSandbox({ exercise, onSuccess }: PythonSandboxProps) {
  const [code, setCode] = useState(exercise.starterCode);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const { runPythonCode, isExecuting, isReady } = usePythonSandbox();

  // Reset if exercise changes
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setCode(exercise.starterCode);
    setOutput("");
    setError(null);
    setIsSuccess(false);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [exercise]);

  const handleRun = async () => {
    if (isExecuting || !isReady) return;

    // We append the hidden test code to the user's code
    const fullCode = `${code}\n\n${exercise.testCode}`;

    setOutput("Executing...\n");
    setError(null);
    setIsSuccess(false);

    const result = await runPythonCode(fullCode);

    setOutput(result.output);

    if (result.error) {
      setError(result.error);
    } else {
      setIsSuccess(true);
      onSuccess();
    }
  };

  const handleReset = () => {
    setCode(exercise.starterCode);
    setOutput("");
    setError(null);
    setIsSuccess(false);
  };

  return (
    <div className="flex flex-col gap-4 w-full border-4 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface dark:bg-[#151411]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#1f1c18]">
        <h3 className="font-black text-lg flex items-center gap-2">
          🐍 Python Sandbox
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-black hover:text-white dark:hover:bg-[#f0ebe2] dark:hover:text-black transition-colors"
          >
            <RotateCcw className="w-4 h-4" /> Reset
          </button>
          <button
            onClick={handleRun}
            disabled={isExecuting || !isReady}
            className="flex items-center gap-2 px-4 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] bg-accent text-white rounded-lg hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <Play className="w-4 h-4" />
            {isExecuting ? "Running..." : "Run"}
          </button>
        </div>
      </div>

      {/* Prompt */}
      {exercise.prompt && (
        <div className="px-4 py-3 bg-blue-50 dark:bg-blue-900/20 border-b-4 border-black dark:border-[#2e2924] text-sm font-medium">
          {exercise.prompt}
        </div>
      )}

      {/* Editor */}
      <div className="p-4 font-mono text-sm bg-white dark:bg-[#151411]">
        <Editor
          value={code}
          onValueChange={(code) => setCode(code)}
          highlight={(code) =>
            Prism.highlight(code, Prism.languages.python, "python")
          }
          padding={10}
          style={{
            fontFamily: '"Fira Code", "JetBrains Mono", monospace',
            fontSize: 14,
            minHeight: "200px",
            backgroundColor: "transparent",
            outline: "none",
          }}
          textareaClassName="focus:outline-none"
        />
      </div>

      {/* Output Console */}
      <div className="p-4 border-t-4 border-black dark:border-[#2e2924] bg-[#1e1e1e] text-white min-h-[120px] max-h-[300px] overflow-y-auto font-mono text-sm">
        <div className="text-gray-400 mb-2 text-xs uppercase font-bold tracking-wider">
          Console Output
        </div>
        {output ? (
          <pre className="whitespace-pre-wrap">{output}</pre>
        ) : (
          <div className="text-gray-500 italic">No output...</div>
        )}

        {error && (
          <div className="mt-4 pt-4 border-t border-red-900/50">
            <div className="flex items-center gap-2 text-red-400 font-bold mb-2">
              <XCircle className="w-4 h-4" /> Runtime Error
            </div>
            <pre className="text-red-300 whitespace-pre-wrap">{error}</pre>
            {exercise.hint && (
              <div className="mt-2 text-yellow-300 text-xs flex gap-2 p-2 bg-yellow-900/20 rounded">
                <span className="font-bold">Hint:</span> {exercise.hint}
              </div>
            )}
          </div>
        )}

        {isSuccess && (
          <div className="mt-4 pt-4 border-t border-green-900/50">
            <div className="flex items-center gap-2 text-green-400 font-bold">
              <CheckCircle2 className="w-5 h-5" /> All tests passed! You earned
              points.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
