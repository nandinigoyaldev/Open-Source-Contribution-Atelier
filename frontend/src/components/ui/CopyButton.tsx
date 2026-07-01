import { useState } from "react";
import Tooltip from "./Tooltip";
type CopyButtonProps = {
  text: string;
};

export default function CopyButton({ text }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);

      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  return (
    <Tooltip content={copied ? "Copied!" : "Copy code"}>
      <button
        type="button"
        onClick={handleCopy}
        className="rounded-lg border-2 border-black bg-surface-low px-3 py-1 text-xs font-black text-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all cursor-pointer"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </Tooltip>
  );
}
