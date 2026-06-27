import React, { useCallback } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-rust";
import "prismjs/themes/prism-tomorrow.css";

interface CodeEditorProps {
  code: string;
  onChange: (code: string) => void;
  language?: string;
  placeholder?: string;
  minHeight?: string;
}

function getGrammar(language: string): Prism.Grammar | null {
  switch (language) {
    case "rust":
      return Prism.languages.rust ?? null;
    case "python":
    default:
      return Prism.languages.python ?? null;
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function CodeEditor({
  code,
  onChange,
  language = "python",
  placeholder,
  minHeight = "200px",
}: CodeEditorProps) {
  const highlight = useCallback(
    (code: string) => {
      const grammar = getGrammar(language);
      if (!grammar) {
        return escapeHtml(code);
      }
      try {
        return Prism.highlight(code, grammar, language);
      } catch {
        return escapeHtml(code);
      }
    },
    [language],
  );

  return (
    <div className="font-mono text-sm bg-white dark:bg-[#151411]">
      <Editor
        value={code}
        onValueChange={onChange}
        highlight={highlight}
        padding={10}
        placeholder={placeholder}
        style={{
          fontFamily: '"Fira Code", "JetBrains Mono", monospace',
          fontSize: 14,
          minHeight,
          backgroundColor: "transparent",
          outline: "none",
        }}
        textareaClassName="focus:outline-none"
      />
    </div>
  );
}
