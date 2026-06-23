import React, { useMemo } from 'react';
import SimpleMdeReact from "react-simplemde-editor";
import "easymde/dist/easymde.min.css";

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  maxLength?: number;
  id?: string;
  className?: string;
}

export function RichTextEditor({ value, onChange, placeholder, disabled, maxLength, id, className }: RichTextEditorProps) {
  const options = useMemo(() => {
    return {
      spellChecker: false,
      placeholder: placeholder || "Type your markdown here...",
      status: ["lines", "words", "cursor"],
      toolbar: [
        "bold", "italic", "heading", "|",
        "quote", "unordered-list", "ordered-list", "|",
        "link", "code", "table", "|",
        "preview", "side-by-side", "fullscreen", "|",
        "guide"
      ],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any;
  }, [placeholder]);

  return (
    <div className={`rich-text-editor-wrapper ${className || ''} ${disabled ? 'opacity-60 pointer-events-none' : ''}`} data-testid="rich-text-editor">
      <div className="border-4 border-black rounded-xl overflow-hidden bg-white dark:bg-[#151411] dark:border-[#2e2924]">
        <SimpleMdeReact 
          id={id}
          value={value} 
          onChange={onChange} 
          options={options} 
        />
      </div>
      {maxLength && (
        <p
          className={`text-xs font-black text-right mt-1 ${
            value.length > maxLength ? "text-red-600" : "text-muted dark:text-[#c4bbae]"
          }`}
        >
          {value.length} / {maxLength} characters
        </p>
      )}
    </div>
  );
}
