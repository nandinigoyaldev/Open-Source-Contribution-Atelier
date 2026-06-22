import React from "react";

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
}

export function ResponsiveTable<T>({
  columns,
  data,
  keyExtractor,
  rowClassName,
  emptyMessage = "No data available",
}: ResponsiveTableProps<T>) {
  return (
    <div className="w-full">
      {/* Mobile Card Layout (Visible < sm) */}
      <div className="block sm:hidden space-y-4">
        {data.length === 0 ? (
          <div className="p-8 text-center text-muted font-bold bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl">
            {emptyMessage}
          </div>
        ) : (
          data.map((item, idx) => (
            <div
              key={keyExtractor(item, idx)}
              className={`rounded-2xl border-4 border-black shadow-card-sm p-4 bg-white dark:bg-[#151411] dark:border-[#2e2924] flex flex-col gap-3 ${rowClassName ? rowClassName(item, idx) : ""}`}
            >
              {columns.map((col, colIdx) => {
                const cellContent =
                  typeof col.accessor === "function"
                    ? col.accessor(item, idx)
                    : (item[col.accessor] as React.ReactNode);
                
                return (
                  <div key={colIdx} className="flex justify-between items-center gap-4 border-b border-dashed border-black/10 dark:border-[#2e2924]/50 pb-2 last:border-0 last:pb-0">
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
          ))
        )}
      </div>

      {/* Desktop Table Layout (Visible >= sm) */}
      <div className="hidden sm:block overflow-x-auto rounded-2xl border-4 border-black shadow-card-sm dark:border-[#2e2924]">
        <table className="w-full border-collapse bg-white dark:bg-[#1f1c18] text-left text-sm font-bold">
          <thead>
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
            ) : (
              data.map((item, idx) => (
                <tr
                  key={keyExtractor(item, idx)}
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
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
