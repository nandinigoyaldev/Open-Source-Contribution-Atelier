import React from "react";
import toast from "react-hot-toast";
import { Info, Trophy, MessageSquare, AlertCircle } from "lucide-react";

export function showNotificationToast(title: string, message: string, type: string) {
  const getIcon = () => {
    switch (type) {
      case "badge":
      case "achievement":
        return <Trophy className="text-[#F1C40F]" size={20} />;
      case "comment":
        return <MessageSquare className="text-[#4f46e5]" size={20} />;
      case "alert":
      case "system":
        return <AlertCircle className="text-red-500" size={20} />;
      default:
        return <Info className="text-gray-500" size={20} />;
    }
  };

  toast.custom(
    (t) => (
      <div
        className={`
          ${t.visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}
          max-w-md w-full bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] shadow-[4px_4px_0px_#000] dark:shadow-[4px_4px_0px_#2e2924] rounded-2xl pointer-events-auto flex p-4 cursor-pointer hover:bg-surface-low dark:hover:bg-[#151411] transition-all duration-300 ease-out
        `}
        onClick={() => toast.dismiss(t.id)}
      >
        <div className="flex-1 w-0 flex items-start gap-3">
          <div className="flex-shrink-0 pt-0.5">{getIcon()}</div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-black text-black dark:text-white uppercase leading-none mb-1">
              {title}
            </p>
            <p className="text-xs text-gray-500 dark:text-[#c4bbae] font-bold line-clamp-2">
              {message}
            </p>
          </div>
        </div>
      </div>
    ),
    { duration: 5000 }
  );
}
