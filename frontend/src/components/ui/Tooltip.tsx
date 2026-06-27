import { ReactNode } from "react";

type TooltipProps = {
  content: string;
  children: ReactNode;
};

export default function Tooltip({ content, children }: TooltipProps) {
  return (
    <div className="relative inline-flex items-center group">
      {children}

      <div
        role="tooltip"
        className="absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-black px-2 py-1 text-xs font-medium text-white opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100 pointer-events-none z-50"
      >
        {content}
      </div>
    </div>
  );
}
