import React, { useEffect, useState } from "react";
import { fetchApi } from "../../lib/api";
import { Download, ArrowLeft, Calendar, FileText } from "lucide-react";
import { getAccessToken } from "../../lib/authToken";
import toast from "react-hot-toast";

interface Invoice {
  id: number;
  stripe_invoice_id: string | null;
  amount: string;
  status: string;
  pdf_url: string | null;
  created_at: string;
}

export function InvoiceHistoryPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchInvoices = async () => {
      try {
        const data = await fetchApi("/billing/invoices/");
        setInvoices(data);
      } catch (err) {
        console.error("Failed to load invoices:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchInvoices();
  }, []);

  const handleDownload = async (invoiceId: number) => {
    toast.success("Downloading invoice PDF...");
    try {
      const getApiBaseUrl = () => {
        if (typeof import.meta !== "undefined" && import.meta.env) {
          return import.meta.env.VITE_API_BASE_URL;
        }
        return "";
      };
      const apiBase = getApiBaseUrl()?.trim() || "http://127.0.0.1:8000/api";
      const token = getAccessToken();

      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(
        `${apiBase}/billing/invoices/${invoiceId}/download/`,
        {
          headers,
        },
      );

      if (!response.ok) {
        throw new Error("Failed to download invoice PDF");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `invoice_${invoiceId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      toast.error(err.message || "Failed to download invoice PDF");
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="text-xl font-bold uppercase animate-pulse text-black dark:text-white">
          Loading billing statement history...
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Back to Billing */}
      <div className="mb-6">
        <a
          href="/settings/billing"
          className="inline-flex items-center gap-2 text-sm font-bold text-gray-500 hover:text-black dark:hover:text-white transition-colors"
        >
          <ArrowLeft size={16} />
          <span>Back to Billing</span>
        </a>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white uppercase mb-2">
          Invoice History
        </h1>
        <p className="text-gray-500 dark:text-[#c4bbae] font-bold">
          Review details of payments and retrieve copies of past billing
          invoices.
        </p>
      </div>

      {/* Invoices List */}
      {invoices.length > 0 ? (
        <div className="overflow-x-auto rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card bg-white dark:bg-[#151411]">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b-4 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
                <th className="p-4 font-black uppercase text-xs text-black dark:text-white">
                  Invoice ID
                </th>
                <th className="p-4 font-black uppercase text-xs text-black dark:text-white">
                  Date
                </th>
                <th className="p-4 font-black uppercase text-xs text-black dark:text-white">
                  Amount
                </th>
                <th className="p-4 font-black uppercase text-xs text-black dark:text-white">
                  Status
                </th>
                <th className="p-4 font-black text-center uppercase text-xs text-black dark:text-white">
                  PDF
                </th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-black dark:divide-[#2e2924]">
              {invoices.map((inv) => (
                <tr
                  key={inv.id}
                  className="hover:bg-gray-50 dark:hover:bg-[#1f1c18]/50 transition-colors"
                >
                  <td className="p-4 font-bold text-sm text-black dark:text-white flex items-center gap-2 mt-1">
                    <FileText size={16} className="text-gray-400 shrink-0" />
                    <span>
                      {inv.stripe_invoice_id || `inv_local_${inv.id}`}
                    </span>
                  </td>
                  <td className="p-4 text-sm font-semibold text-gray-600 dark:text-[#c4bbae]">
                    <span className="flex items-center gap-1.5">
                      <Calendar size={14} className="text-gray-400 shrink-0" />
                      {new Date(inv.created_at).toLocaleDateString()}
                    </span>
                  </td>
                  <td className="p-4 text-sm font-black text-black dark:text-white">
                    ${parseFloat(inv.amount).toFixed(2)}
                  </td>
                  <td className="p-4">
                    <span
                      className={`inline-block px-2 py-0.5 text-xs font-black uppercase border-2 rounded-full ${
                        inv.status === "paid"
                          ? "bg-green-50 text-green-700 border-green-400"
                          : "bg-yellow-50 text-yellow-700 border-yellow-400"
                      }`}
                    >
                      {inv.status}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <button
                      onClick={() => handleDownload(inv.id)}
                      className="inline-flex items-center justify-center p-2 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] hover:bg-primary hover:text-black transition-all"
                      title="Download PDF"
                    >
                      <Download size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-8 text-center shadow-card">
          <p className="text-gray-500 dark:text-[#c4bbae] font-bold">
            No billing statements or invoices found in your account history.
          </p>
        </div>
      )}
    </div>
  );
}

export default InvoiceHistoryPage;
