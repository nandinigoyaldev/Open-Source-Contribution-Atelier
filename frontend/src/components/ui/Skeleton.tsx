import React from "react";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function Skeleton({ className = "", ...props }: SkeletonProps) {
  return (
    <div
      className={`animate-shimmer bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] rounded ${className}`}
      {...props}
    />
  );
}
