import React, { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

export interface ColumnDef<T> {
  header: React.ReactNode;
  accessor: keyof T | ((item: T, index: number) => React.ReactNode);
  className?: string;
  label?: string; // used for the mobile card layout if header is complex
}

interface ResponsiveTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  keyExtractor: (item: T, index: number) => string;
  rowClassName?: (item: T, index: number) => string;
  emptyMessage?: React.ReactNode;
  lastElementRef?: (node: Element | null) => void;
  footerContent?: React.ReactNode;
  virtualized?: boolean;
  containerHeight?: string;
}

export function ResponsiveTable<T>({
  columns,
  data,
  keyExtractor,
  rowClassName,
  emptyMessage = "No data available",
  lastElementRef,
  footerContent,
  virtualized = false,
  containerHeight = "600px",
}: ResponsiveTableProps<T>) {
  const mobileParentRef = useRef<HTMLDivElement>(null);
  const desktopParentRef = useRef<HTMLDivElement>(null);

  const mobileVirtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => mobileParentRef.current,
    estimateSize: () => 150,
  });

  const desktopVirtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => desktopParentRef.current,
    estimateSize: () => 50,
  });

  const mobileVirtualItems = mobileVirtualizer.getVirtualItems();
  const desktopVirtualItems = desktopVirtualizer.getVirtualItems();

  const renderMobileItem = (item: T, idx: number, measureRef?: (node: Element | null) => void) => {
    const isLast = idx === data.length - 1;
    return (
      <div
        key={keyExtractor(item, idx)}
        ref={(node) => {
          if (measureRef) measureRef(node);
          if (isLast && lastElementRef) lastElementRef(node);
        }}
        data-index={idx}
        className={`rounded-2xl border-4 border-black shadow-card-sm p-4 bg-white dark:bg-[#151411] dark:border-[#2e2924] flex flex-col gap-3 ${rowClassName ? rowClassName(item, idx) : ""}`}
      >
        {columns.map((col, colIdx) => {
          const cellContent =
            typeof col.accessor === "function"
              ? col.accessor(item, idx)
              : (item[col.accessor] as React.ReactNode);

          return (
            <div
              key={colIdx}
              className="flex justify-between items-center gap-4 border-b border-dashed border-black/10 dark:border-[#2e2924]/50 pb-2 last:border-0 last:pb-0"
            >
              <span className="text-xs uppercase tracking-wider font-black text-muted dark:text-[#c4bbae]">
                {col.label || col.header}
              </span>
              <div className="text-sm font-bold text-right truncate flex-1 flex justify-end">
                {cellContent}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderDesktopItem = (item: T, idx: number, measureRef?: (node: Element | null) => void) => {
    const isLast = idx === data.length - 1;
    return (
      <tr
        key={keyExtractor(item, idx)}
        ref={(node) => {
          if (measureRef) measureRef(node);
          if (isLast && lastElementRef) lastElementRef(node);
        }}
        data-index={idx}
        className={`border-b-2 border-black last:border-b-0 hover:bg-surface-lowest transition dark:border-[#2e2924] dark:hover:bg-black/10 ${rowClassName ? rowClassName(item, idx) : ""}`}
      >
        {columns.map((col, colIdx) => (
          <td
            key={colIdx}
            className={`px-4 py-3 border-r-2 border-black dark:border-[#2e2924] last:border-r-0 ${col.className || ""}`}
          >
            {typeof col.accessor === "function"
              ? col.accessor(item, idx)
              : (item[col.accessor] as React.ReactNode)}
          </td>
        ))}
      </tr>
    );
  };

  return (
    <div className="w-full">
      {/* Mobile Card Layout (Visible < sm) */}
      <div 
        ref={mobileParentRef}
        className={`block sm:hidden ${virtualized ? 'overflow-y-auto' : 'space-y-4'}`}
        style={virtualized ? { maxHeight: containerHeight } : undefined}
      >
        {data.length === 0 ? (
          <div className="p-8 text-center text-muted font-bold bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl">
            {emptyMessage}
          </div>
        ) : virtualized ? (
          <div className="relative w-full" style={{ height: `${mobileVirtualizer.getTotalSize()}px` }}>
            {mobileVirtualItems.map(virtualRow => (
              <div
                key={virtualRow.key}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`
                }}
                className="pb-4"
              >
                {renderMobileItem(data[virtualRow.index], virtualRow.index, mobileVirtualizer.measureElement)}
              </div>
            ))}
          </div>
        ) : (
          data.map((item, idx) => renderMobileItem(item, idx))
        )}
        
        {footerContent && (
          <div className="p-4 mt-4 text-center text-sm text-muted animate-pulse font-bold bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl">
            {footerContent}
          </div>
        )}
      </div>

      {/* Desktop Table Layout (Visible >= sm) */}
      <div 
        ref={desktopParentRef}
        className={`hidden sm:block overflow-x-auto rounded-2xl border-4 border-black shadow-card-sm dark:border-[#2e2924] ${virtualized ? 'overflow-y-auto' : ''}`}
        style={virtualized ? { maxHeight: containerHeight } : undefined}
      >
        <table className="w-full border-collapse bg-white dark:bg-[#1f1c18] text-left text-sm font-bold relative">
          <thead className={virtualized ? "sticky top-0 z-10" : ""}>
            <tr className="bg-surface-low border-b-4 border-black dark:bg-[#151411] dark:border-[#2e2924]">
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className={`px-4 py-3 text-xs uppercase tracking-wider border-r-2 border-black dark:border-[#2e2924] last:border-r-0 ${col.className || ""}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-muted font-bold"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : virtualized ? (
              <>
                {desktopVirtualItems.length > 0 && desktopVirtualItems[0].start > 0 && (
                  <tr>
                    <td style={{ height: `${desktopVirtualItems[0].start}px` }} colSpan={columns.length} />
                  </tr>
                )}
                {desktopVirtualItems.map(virtualRow => 
                  renderDesktopItem(data[virtualRow.index], virtualRow.index, desktopVirtualizer.measureElement)
                )}
                {desktopVirtualItems.length > 0 && desktopVirtualItems[desktopVirtualItems.length - 1].end < desktopVirtualizer.getTotalSize() && (
                  <tr>
                    <td style={{ height: `${desktopVirtualizer.getTotalSize() - desktopVirtualItems[desktopVirtualItems.length - 1].end}px` }} colSpan={columns.length} />
                  </tr>
                )}
              </>
            ) : (
              data.map((item, idx) => renderDesktopItem(item, idx))
            )}
            
            {footerContent && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-4 text-center text-sm text-muted animate-pulse font-bold border-t-2 border-black dark:border-[#2e2924]"
                >
                  {footerContent}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
