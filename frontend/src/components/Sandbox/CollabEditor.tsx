import React, { useEffect, useRef } from "react";
import MonacoEditor, { OnMount } from "@monaco-editor/react";
import * as Y from "yjs";
import { MonacoBinding } from "y-monaco";
import { WebsocketProvider } from "y-websocket";
import type { editor } from "monaco-editor";

interface CollabEditorProps {
  fileId: string;
  language: string;
  ydoc: React.MutableRefObject<Y.Doc | null>;
  provider: React.MutableRefObject<WebsocketProvider | null>;
  readOnly?: boolean;
  onSelectLine?: (line: number) => void;
}

export function CollabEditor({
  fileId,
  language,
  ydoc,
  provider,
  readOnly = false,
  onSelectLine,
}: CollabEditorProps) {
  const bindingRef = useRef<MonacoBinding | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleEditorDidMount: OnMount = (editorInstance, monacoInstance) => {
    editorRef.current = editorInstance;

    if (!ydoc.current || !provider.current) return;

    // Each file gets its own Y.Text keyed by fileId
    const yText = ydoc.current.getText(fileId);

    bindingRef.current = new MonacoBinding(
      yText,
      editorInstance.getModel()!,
      new Set([editorInstance]),
      provider.current.awareness,
    );

    // Track line selection
    editorInstance.onDidChangeCursorPosition((e) => {
      onSelectLine?.(e.position.lineNumber);
    });

    // Suppress unused variable warning – monacoInstance used for type inference
    void monacoInstance;
  };

  // Destroy binding when file changes
  useEffect(() => {
    return () => {
      bindingRef.current?.destroy();
      bindingRef.current = null;
    };
  }, [fileId]);

  return (
    <MonacoEditor
      height="100%"
      language={language}
      theme="vs-dark"
      options={{
        readOnly,
        fontSize: 14,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        wordWrap: "on",
        automaticLayout: true,
        cursorBlinking: "smooth",
      }}
      onMount={handleEditorDidMount}
    />
  );
}
