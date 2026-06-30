import React, { useState, useRef, useCallback } from "react";

export interface WidgetConfig {
  id: string;
  label: string;
}

interface DraggableWidgetGridProps {
  widgets: WidgetConfig[];
  onReorder: (newOrder: WidgetConfig[]) => void;
  children: React.ReactNode[];
}

export function DraggableWidgetGrid({
  widgets,
  onReorder,
  children,
}: DraggableWidgetGridProps) {
  const dragIndex = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const handleDragStart = useCallback((index: number) => {
    dragIndex.current = index;
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex.current === null || dragIndex.current === index) return;
    setDragOverIndex(index);
  }, []);

  const handleDrop = useCallback(
    (index: number) => {
      if (dragIndex.current === null || dragIndex.current === index) {
        setDragOverIndex(null);
        return;
      }
      const newWidgets = [...widgets];
      const [moved] = newWidgets.splice(dragIndex.current, 1);
      newWidgets.splice(index, 0, moved);
      dragIndex.current = null;
      setDragOverIndex(null);
      onReorder(newWidgets);
    },
    [widgets, onReorder]
  );

  const handleDragEnd = useCallback(() => {
    dragIndex.current = null;
    setDragOverIndex(null);
  }, []);

  return (
    <div className="space-y-10">
      {widgets.map((widget, index) => (
        <div
          key={widget.id}
          draggable
          onDragStart={() => handleDragStart(index)}
          onDragOver={(e) => handleDragOver(e, index)}
          onDrop={() => handleDrop(index)}
          onDragEnd={handleDragEnd}
          className={`transition-all duration-200 ${
            dragOverIndex === index
              ? "ring-4 ring-primary ring-offset-2 rounded-[2rem] scale-[1.01] opacity-80"
              : ""
          }`}
        >
          <div className="flex justify-end mb-1 pr-1">
            <span
              title={`Drag to reorder: ${widget.label}`}
              className="text-[10px] font-black text-muted/50 hover:text-muted cursor-grab active:cursor-grabbing select-none uppercase tracking-widest flex items-center gap-1 dark:text-[#c4bbae]/40"
            >
              ⠿ drag to reorder
            </span>
          </div>
          {children[index]}
        </div>
      ))}
    </div>
  );
}