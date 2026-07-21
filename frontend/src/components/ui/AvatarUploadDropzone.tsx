import React, { useState, useRef, useEffect } from "react";
import { UploadCloud, X } from "lucide-react";
import { useToast } from "../../features/ui/ToastContext";
import { getMediaUrl } from "../../lib/api";

interface AvatarUploadDropzoneProps {
  currentAvatarUrl?: string | null;
  onFileSelect: (file: File | null) => void;
}

export function AvatarUploadDropzone({
  currentAvatarUrl,
  onFileSelect,
}: AvatarUploadDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(
    getMediaUrl(currentAvatarUrl) || null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  useEffect(() => {
    setPreviewUrl(getMediaUrl(currentAvatarUrl) || null);
  }, [currentAvatarUrl]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file: File) => {
    // Validate file type
    if (!file.type.startsWith("image/")) {
      addToast("Please upload an image file (JPEG, PNG, WebP).", "error");
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      addToast("File is too large. Maximum size is 5MB.", "error");
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    onFileSelect(file);
  };

  const clearImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setPreviewUrl(null);
    onFileSelect(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div className="w-full mb-5">
      <label className="block text-xs font-bold text-text dark:text-[#f0ebe2] mb-1.5 uppercase tracking-wide">
        Profile Picture
      </label>
      <div
        className={`relative w-full h-28 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all duration-200 bg-white/50 dark:bg-[linear-gradient(145deg,#181f2c,#12110f)] dark:shadow-[0_12px_26px_rgba(0,0,0,0.28)_inset] ${
          dragActive
            ? "border-primary bg-primary/10 scale-[1.01]"
            : "border-black/30 hover:border-primary dark:border-[#5d5247] dark:hover:border-accent"
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleChange}
        />

        {previewUrl ? (
          <div className="relative group p-1.5">
            <div className="relative w-20 h-20 rounded-full overflow-hidden border-2 border-gray-800 shadow-lg transition-transform group-hover:scale-105">
              <img
                src={previewUrl}
                alt="Avatar preview"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <span className="text-white text-[10px] font-semibold drop-shadow-md">
                  Change
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={clearImage}
              className="absolute top-0 right-0 p-1 bg-red-500 rounded-full text-white hover:bg-red-600 transition-colors shadow shadow-red-700/50 hover:scale-105 z-10"
              title="Remove image"
            >
              <X size={12} strokeWidth={3} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center text-muted dark:text-[#c4bbae] p-3 text-center">
            <div className="w-10 h-10 rounded-full bg-[#1f2937] dark:bg-[#2e2924] flex items-center justify-center mb-1.5 shadow-inner">
              <UploadCloud size={20} className="text-[#8a8fff]" />
            </div>
            <p className="text-sm font-bold text-text dark:text-[#f0ebe2]">
              Click or drag image to upload
            </p>
            <p className="text-[10px] text-muted dark:text-[#c4bbae] mt-0.5">
              JPG, PNG, WebP (max. 5MB)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
