import React, { useState, useEffect, useRef, useCallback } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import axe from "axe-core";
import { AlertTriangle, Info, XCircle, CheckCircle } from "lucide-react";

type A11yIssue = axe.Result;

export function A11yLinterSandbox() {
  const [code, setCode] = useState(
    `<main>\n  <h1>Welcome</h1>\n  <img src="cat.jpg" />\n  <button></button>\n</main>`
  );
  const [issues, setIssues] = useState<A11yIssue[]>([]);
  const [ignoredRules, setIgnoredRules] = useState<Set<string>>(new Set());
  
  const containerRef = useRef<HTMLDivElement>(null);
  const monaco = useMonaco();
  const editorRef = useRef<any>(null);
  const decorationsRef = useRef<string[]>([]);

  const analyzeAccessibility = useCallback(async () => {
    if (!containerRef.current) return;

    try {
      const results = await axe.run(containerRef.current, {
        rules: {
          // You can disable rules here based on ignoredRules
        }
      });

      const filteredIssues = results.violations.filter(
        v => !ignoredRules.has(v.id)
      );
      setIssues(filteredIssues);
      
      updateDecorations(filteredIssues);
    } catch (err) {
      console.error("Axe core error:", err);
    }
  }, [code, ignoredRules]);

  useEffect(() => {
    const timer = setTimeout(() => {
      analyzeAccessibility();
    }, 500); // debounce
    return () => clearTimeout(timer);
  }, [code, analyzeAccessibility]);

  const updateDecorations = (violations: A11yIssue[]) => {
    if (!monaco || !editorRef.current) return;

    // Simple mapping: we just highlight the whole editor or find lines if possible.
    // Realistically, axe gives DOM nodes. We can try to map DOM nodes back to lines in code if we have a parser,
    // but for a simple implementation, we can highlight the first line or just show the panel.
    // For a more advanced setup, we would parse HTML to get line numbers of violations.
    
    // As a rudimentary approach without an HTML AST parser:
    const newDecorations: any[] = [];
    
    violations.forEach(v => {
      v.nodes.forEach(node => {
        // try to find the HTML snippet in code
        const snippet = node.html;
        const lines = code.split('\n');
        
        let foundLine = -1;
        let foundCol = -1;
        
        for (let i = 0; i < lines.length; i++) {
          if (lines[i].includes(snippet)) {
            foundLine = i + 1;
            foundCol = lines[i].indexOf(snippet) + 1;
            break;
          }
        }
        
        // If exact snippet not found, just use node target selector roughly
        if (foundLine === -1 && typeof node.target[0] === 'string') {
          const targetStr = node.target[0] as string;
          const tagMatch = targetStr.match(/^([a-z0-9]+)/i);
          if (tagMatch) {
            const tag = `<${tagMatch[1]}`;
            for (let i = 0; i < lines.length; i++) {
              if (lines[i].includes(tag)) {
                foundLine = i + 1;
                foundCol = lines[i].indexOf(tag) + 1;
                break;
              }
            }
          }
        }

        if (foundLine !== -1) {
          newDecorations.push({
            range: new monaco.Range(foundLine, foundCol, foundLine, foundCol + (snippet ? snippet.length : 10)),
            options: {
              isWholeLine: false,
              className: 'a11y-error-decoration',
              glyphMarginClassName: 'a11y-error-glyph',
              hoverMessage: { value: `**A11y Issue: ${v.id}**\n\n${v.help}\n\n${node.failureSummary}` },
              inlineClassName: 'decoration-wavy decoration-red-500 underline-offset-4 decoration-2 underline'
            }
          });
        }
      });
    });

    decorationsRef.current = editorRef.current.deltaDecorations(
      decorationsRef.current,
      newDecorations
    );
  };

  const toggleIgnoreRule = (ruleId: string) => {
    setIgnoredRules(prev => {
      const next = new Set(prev);
      if (next.has(ruleId)) next.delete(ruleId);
      else next.add(ruleId);
      return next;
    });
  };

  const getSeverityIcon = (impact?: string | null) => {
    switch (impact) {
      case 'critical':
      case 'serious':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'moderate':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  return (
    <div className="flex h-full gap-4 flex-col lg:flex-row">
      <div className="flex flex-col flex-1 bg-surface-lowest border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
        <div className="flex items-center justify-between border-b-4 border-black dark:border-[#2e2924] bg-surface-low px-4 py-2 dark:bg-[#151411]">
          <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2] flex items-center gap-2">
            <span>♿</span> A11y Code Editor
          </h3>
        </div>
        <div className="flex-1 relative">
          <Editor
            height="100%"
            defaultLanguage="html"
            value={code}
            onChange={(val) => setCode(val || "")}
            theme="vs-dark"
            onMount={(editor) => { editorRef.current = editor; }}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: "on",
              padding: { top: 16 },
            }}
          />
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-4">
        {/* Hidden container for axe-core evaluation */}
        <div
          ref={containerRef}
          style={{ position: 'absolute', left: '-9999px', top: '-9999px', width: '1000px', height: '1000px', overflow: 'hidden' }}
          dangerouslySetInnerHTML={{ __html: code }}
        />

        <div className="flex-1 bg-surface-lowest border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card flex flex-col">
          <div className="border-b-4 border-black dark:border-[#2e2924] bg-surface-low px-4 py-2 dark:bg-[#151411]">
            <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">
              Accessibility Issues ({issues.length})
            </h3>
          </div>
          <div className="flex-1 overflow-auto p-4 flex flex-col gap-3">
            {issues.length === 0 ? (
              <div className="flex items-center gap-2 text-green-500 font-bold p-4 bg-green-500/10 rounded-lg">
                <CheckCircle className="w-5 h-5" />
                No accessibility issues found!
              </div>
            ) : (
              issues.map(issue => (
                <div key={issue.id} className="border-2 border-black dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-[#1a1b26]">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2 font-bold mb-1 text-text dark:text-[#a9b1d6]">
                      {getSeverityIcon(issue.impact)}
                      {issue.help}
                    </div>
                    <button
                      onClick={() => toggleIgnoreRule(issue.id)}
                      className="text-xs px-2 py-1 bg-gray-200 dark:bg-gray-800 rounded hover:bg-gray-300 dark:hover:bg-gray-700 font-bold"
                    >
                      Ignore
                    </button>
                  </div>
                  <p className="text-sm text-muted dark:text-gray-400 mb-2">
                    {issue.description}
                  </p>
                  <div className="flex flex-col gap-2">
                    {issue.nodes.map((node, i) => (
                      <div key={i} className="text-xs bg-gray-100 dark:bg-[#151411] p-2 rounded border border-gray-200 dark:border-gray-800">
                        <code className="text-pink-500 font-mono block mb-1">{node.target.join(", ")}</code>
                        <span className="text-gray-600 dark:text-gray-400">{node.failureSummary}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
