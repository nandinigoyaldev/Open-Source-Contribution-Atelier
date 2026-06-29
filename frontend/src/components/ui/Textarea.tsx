import React, { useRef, type TextareaHTMLAttributes } from "react";
import { useAutoResize } from "../../hooks/useAutoResize";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  autoResize?: boolean;
}

export function Textarea({
  autoResize = true,
  className = "",
  ...props
}: TextareaProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useAutoResize(ref, [autoResize]);

  return (
    <textarea
      ref={ref}
      className={`${autoResize ? "resize-none " : ""}${className}`}
      {...props}
    />
  );
}
