import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from "lucide-react";
import { ToastMessage, ToastType } from "../../features/ui/ToastContext";

interface ToastProps {
  toast: ToastMessage;
  onClose: (id: string) => void;
}

const getToastStyles = (type: ToastType) => {
  switch (type) {
    case "success":
      return "bg-green-100 border-green-500 text-green-900";
    case "error":
      return "bg-red-100 border-red-500 text-red-900";
    case "warning":
      return "bg-yellow-100 border-yellow-500 text-yellow-900";
    case "info":
      return "bg-blue-100 border-blue-500 text-blue-900";
    default:
      return "bg-white border-gray-500 text-gray-900";
  }
};

const getToastIcon = (type: ToastType) => {
  switch (type) {
    case "success":
      return <CheckCircle2 className="w-6 h-6 text-green-600" />;
    case "error":
      return <XCircle className="w-6 h-6 text-red-600" />;
    case "warning":
      return <AlertTriangle className="w-6 h-6 text-yellow-600" />;
    case "info":
      return <Info className="w-6 h-6 text-blue-600" />;
    default:
      return <Info className="w-6 h-6 text-gray-600" />;
  }
};

const Toast: React.FC<ToastProps> = ({ toast, onClose }) => {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 50, scale: 0.3 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.5, transition: { duration: 0.2 } }}
      role={toast.type === "error" ? "alert" : "status"}
      aria-live={toast.type === "error" ? "assertive" : "polite"}
      className={`relative flex items-center gap-3 w-full max-w-sm p-4 rounded-2xl border-4 shadow-card ${getToastStyles(
        toast.type
      )}`}
    >
      <div className="flex-shrink-0">{getToastIcon(toast.type)}</div>
      <div className="flex-1">
        <p className="font-bold text-sm leading-snug">{toast.message}</p>
      </div>
      <button
        onClick={() => onClose(toast.id)}
        className="flex-shrink-0 p-1 hover:bg-black/10 rounded-full transition-colors focus:outline-none"
        aria-label="Close notification"
      >
        <X className="w-4 h-4 opacity-70" />
      </button>
    </motion.div>
  );
};

export const ToastContainer: React.FC<{ toasts: ToastMessage[]; removeToast: (id: string) => void }> = ({
  toasts,
  removeToast,
}) => {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <Toast toast={toast} onClose={removeToast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
};
