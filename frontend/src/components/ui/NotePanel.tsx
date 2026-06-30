import React, { useState, useEffect, useRef, useCallback } from "react";
import { useLessonNote } from "../../hooks/useLessonNote";
import { X, Save, CheckCircle2, AlertCircle } from "lucide-react";

interface NotePanelProps {
  lessonSlug: string;
  onClose: () => void;
}

export function NotePanel({ lessonSlug, onClose }: NotePanelProps) {
  const { note, isLoading, saveNote, isSaving, isError, isSuccess } =
    useLessonNote(lessonSlug);
  const [content, setContent] = useState("");
  const [width, setWidth] = useState(300); // initial width
  const isResizing = useRef(false);
  const saveTimeout = useRef<NodeJS.Timeout | null>(null);

  // Initialize content from the fetched note
  useEffect(() => {
    if (note && note.content !== undefined) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setContent(note.content);
    }
  }, [note]);

  // Autosave logic
  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setContent(newContent);

    if (saveTimeout.current) {
      clearTimeout(saveTimeout.current);
    }

    saveTimeout.current = setTimeout(() => {
      saveNote(newContent);
    }, 1000); // 1-second debounce
  };

  // Resizing logic
  const handleMouseDown = (e: React.MouseEvent) => {
    isResizing.current = true;
    e.preventDefault();
  };

  const handleMouseUp = () => {
    isResizing.current = false;
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current) return;
    const newWidth = document.body.clientWidth - e.clientX;
    // Set min/max widths
    if (newWidth > 200 && newWidth < 600) {
      setWidth(newWidth);
    }
  }, []);

  useEffect(() => {
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [handleMouseMove]);

  return (
    <div
      className="fixed right-0 top-0 h-full bg-white dark:bg-[#151411] border-l-4 border-black dark:border-[#2e2924] flex flex-row z-30 shadow-[-5px_0px_15px_rgba(0,0,0,0.1)] transition-transform duration-300 lg:relative lg:top-auto lg:h-auto lg:shadow-none"
      style={{ width: `${width}px` }}
    >
      {/* Resize Handle */}
      <div
        className="w-2 cursor-col-resize absolute left-0 top-0 h-full hover:bg-black/10 z-10 hidden lg:block"
        onMouseDown={handleMouseDown}
      />

      <div className="flex-1 flex flex-col h-full w-full relative pt-20 lg:pt-0">
        <div className="flex items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924]">
          <h2 className="text-lg font-black uppercase flex items-center gap-2">
            📝 Private Notes
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg border-2 border-black hover:bg-black hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Save Status Indicator */}
        <div className="px-4 py-2 bg-surface-lowest dark:bg-[#0f0e0c] flex items-center gap-2 border-b-2 border-black/10 dark:border-[#2e2924]/40 text-xs font-bold text-muted dark:text-[#c4bbae]">
          {isSaving ? (
            <span className="flex items-center gap-1 text-yellow-600">
              <Save size={14} className="animate-pulse" /> Saving...
            </span>
          ) : isError ? (
            <span className="flex items-center gap-1 text-red-600">
              <AlertCircle size={14} /> Save failed
            </span>
          ) : isSuccess ? (
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle2 size={14} /> Saved
            </span>
          ) : isLoading ? (
            <span className="flex items-center gap-1">Loading...</span>
          ) : (
            <span className="flex items-center gap-1">
              <CheckCircle2 size={14} /> Synced
            </span>
          )}
        </div>

        <div className="flex-1 p-4 bg-surface dark:bg-[#1f1c18]">
          <textarea
            className="w-full h-full resize-none bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-lg p-4 font-mono text-sm outline-none focus:ring-4 focus:ring-accent/50 transition-all dark:text-[#f0ebe2]"
            placeholder="Jot down your thoughts, commands, or anything you want to remember..."
            value={content}
            onChange={handleContentChange}
            disabled={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
