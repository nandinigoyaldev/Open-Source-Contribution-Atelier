import React, { useState, useRef, useEffect } from "react";
import { X, Image as ImageIcon } from "lucide-react";
import { useToast } from "../../features/ui/ToastContext";

interface CoverUploadDropzoneProps {
  currentCoverUrl?: string | null;
  onFileSelect: (file: File | null) => void;
}

export function CoverUploadDropzone({
  currentCoverUrl,
  onFileSelect,
}: CoverUploadDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(
    currentCoverUrl || null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  useEffect(() => {
    if (currentCoverUrl && !previewUrl) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPreviewUrl(currentCoverUrl);
    }
  }, [currentCoverUrl, previewUrl]);

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
    <div className="w-full mb-8">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Profile Cover Image
      </label>
      <div
        className={`relative w-full h-40 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center cursor-pointer transition-all duration-200 overflow-hidden ${
          dragActive
            ? "border-indigo-500 bg-indigo-500/10 scale-[1.02]"
            : "border-gray-700 hover:border-gray-500 hover:bg-gray-800/50"
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
          <div className="relative group w-full h-full">
            <img
              src={previewUrl}
              alt="Cover preview"
              className="w-full h-full object-cover transition-transform group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <span className="text-white text-sm font-semibold drop-shadow-md">
                Change Cover Image
              </span>
            </div>
            <button
              type="button"
              onClick={clearImage}
              className="absolute top-2 right-2 p-1.5 bg-red-500 rounded-full text-white hover:bg-red-600 transition-colors shadow-lg hover:scale-110 z-10"
              title="Remove image"
            >
              <X size={16} strokeWidth={3} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center text-gray-400 p-6 text-center z-10">
            <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-3 shadow-inner">
              <ImageIcon size={24} className="text-indigo-400" />
            </div>
            <p className="text-base font-semibold text-gray-600">
              Upload a banner image
            </p>
            <p className="text-sm text-gray-600 mt-1">
              Supports JPG, PNG, and WebP (max. 5MB). Ideal aspect ratio 3:1.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
