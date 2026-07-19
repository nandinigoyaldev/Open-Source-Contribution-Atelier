import React, { useEffect, useRef, useState } from "react";
import {
  CheckCircle,
  Loader2,
  Pause,
  Play,
  ShieldAlert,
  Upload,
  X,
} from "lucide-react";
import { fetchApi } from "../../lib/api";
import { getAccessToken } from "../../lib/authToken";

const CHUNK_SIZE = 5 * 1024 * 1024;
const TERMINAL_SCAN_STATUSES = new Set([
  "clean",
  "released",
  "infected",
  "rejected",
  "failed",
]);

type UploadStatus =
  | "idle"
  | "uploading"
  | "paused"
  | "quarantined"
  | "scanning"
  | "clean"
  | "released"
  | "infected"
  | "rejected"
  | "failed"
  | "error";

interface ScanStatusResponse {
  status: UploadStatus;
  message?: string;
  file_path?: string | null;
  uploaded_chunks?: number[];
}

export function ChunkedUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const uploadRef = useRef({ abort: false });

  useEffect(() => {
    if (!sessionId || !["quarantined", "scanning"].includes(status)) return;

    const timer = window.setInterval(async () => {
      try {
        const response = (await fetchApi(
          `/uploads/status/${sessionId}/`,
        )) as ScanStatusResponse;
        setStatus(response.status);
        setStatusMessage(response.message ?? "");
        if (TERMINAL_SCAN_STATUSES.has(response.status))
          window.clearInterval(timer);
      } catch {
        setStatus("error");
        setStatusMessage("Unable to retrieve scan status.");
        window.clearInterval(timer);
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [sessionId, status]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    setStatus("idle");
    setProgress(0);
    setSessionId(null);
    setStatusMessage("");
  };

  const startUpload = async () => {
    if (!file) return;

    try {
      setStatus("uploading");
      uploadRef.current.abort = false;
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      let currentSessionId = sessionId;
      let uploadedChunks: number[] = [];

      if (!currentSessionId) {
        const response = await fetchApi("/uploads/start/", {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            total_size: file.size,
            total_chunks: totalChunks,
            upload_type: "project",
          }),
        });
        currentSessionId = response.session_id;
        setSessionId(currentSessionId);
      } else {
        const response = (await fetchApi(
          `/uploads/status/${currentSessionId}/`,
        )) as ScanStatusResponse;
        uploadedChunks = response.uploaded_chunks ?? [];
        setProgress(Math.floor((uploadedChunks.length / totalChunks) * 100));
      }

      for (let index = 0; index < totalChunks; index += 1) {
        if (uploadRef.current.abort) {
          setStatus("paused");
          return;
        }
        if (uploadedChunks.includes(index)) continue;

        const chunk = file.slice(
          index * CHUNK_SIZE,
          Math.min((index + 1) * CHUNK_SIZE, file.size),
        );
        const formData = new FormData();
        formData.append("chunk", chunk);
        formData.append("chunk_index", index.toString());

        // We use fetch directly for FormData
        const token = getAccessToken();
        const chunkRes = await fetch(
          `/api/uploads/chunk/${currentSessionId}/`,
          {
            method: "POST",
            headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            body: formData,
          },
        );

        if (!chunkRes.ok) throw new Error("Chunk upload failed");

        const newProgress = Math.floor(((index + 1) / totalChunks) * 100);
        setProgress(newProgress);
      }

      const completion = await fetchApi(
        `/uploads/complete/${currentSessionId}/`,
        { method: "POST" },
      );
      setStatus(completion.status ?? "quarantined");
      setStatusMessage(completion.message ?? "File is being scanned...");
      setProgress(100);
    } catch (error) {
      setStatus("error");
      setStatusMessage(
        error instanceof Error ? error.message : "Upload failed",
      );
    }
  };

  const cancelUpload = () => {
    uploadRef.current.abort = true;
    setFile(null);
    setStatus("idle");
    setProgress(0);
    setSessionId(null);
    setStatusMessage("");
  };

  const scanning = status === "quarantined" || status === "scanning";
  const successful = status === "clean" || status === "released";
  const blocked =
    status === "infected" || status === "rejected" || status === "failed";

  return (
    <div className="bg-white p-6 rounded-2xl border-4 border-black shadow-card max-w-md w-full dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
      <h2 className="text-2xl font-black mb-4">Upload Large File</h2>
      {!file ? (
        <div className="border-4 border-dashed border-black/20 rounded-xl p-8 text-center relative hover:bg-surface-low transition-colors dark:border-white/10">
          <input
            type="file"
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <Upload className="mx-auto mb-2 text-muted" size={32} />
          <p className="font-bold text-muted">Click or drag file to upload</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="truncate pr-4 font-bold">
              {file.name} ({(file.size / 1048576).toFixed(2)} MB)
            </div>
            {!successful && (
              <button
                onClick={cancelUpload}
                className="text-red-500 p-1"
                aria-label="Cancel upload"
              >
                <X size={20} />
              </button>
            )}
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 dark:bg-gray-800 border-2 border-black dark:border-[#2e2924]">
            <div
              className={`h-full rounded-full transition-all ${blocked || status === "error" ? "bg-red-500" : "bg-primary"}`}
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between gap-3 font-bold text-sm">
            <span className="text-muted">
              {status === "idle" && "Ready to upload"}
              {status === "uploading" && `Uploading... ${progress}%`}
              {status === "paused" && "Paused"}
              {scanning && (statusMessage || "File is being scanned...")}
              {successful && (statusMessage || "Upload complete and verified")}
              {(blocked || status === "error") &&
                (statusMessage || "Upload blocked")}
            </span>
            {scanning && <Loader2 className="animate-spin" size={20} />}
            {successful && <CheckCircle className="text-green-500" size={20} />}
            {blocked && <ShieldAlert className="text-red-500" size={20} />}
            {["idle", "paused", "error"].includes(status) && (
              <button
                onClick={startUpload}
                className="bg-black text-white px-3 py-1 rounded-full text-xs flex items-center gap-1 dark:bg-white dark:text-black"
              >
                <Play size={14} /> {status === "idle" ? "Start" : "Resume"}
              </button>
            )}
            {status === "uploading" && (
              <button
                onClick={() => {
                  uploadRef.current.abort = true;
                }}
                className="bg-black text-white px-3 py-1 rounded-full text-xs flex items-center gap-1"
              >
                <Pause size={14} /> Pause
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
