import React, { useState, useRef, useEffect } from "react";
import { UploadCloud, X } from "lucide-react";
import { useToast } from "../../features/ui/ToastContext";

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
    currentAvatarUrl || null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  useEffect(() => {
    if (currentAvatarUrl && !previewUrl) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPreviewUrl(currentAvatarUrl);
    }
  }, [currentAvatarUrl, previewUrl]);

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
        Profile Picture
      </label>
      <div
        className={`relative w-full h-48 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center cursor-pointer transition-all duration-200 ${
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
          <div className="relative group p-2">
            <div className="relative w-32 h-32 rounded-full overflow-hidden border-4 border-gray-800 shadow-2xl transition-transform group-hover:scale-105">
              <img
                src={previewUrl}
                alt="Avatar preview"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <span className="text-white text-xs font-semibold drop-shadow-md">
                  Change
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={clearImage}
              className="absolute top-0 right-0 p-1.5 bg-red-500 rounded-full text-white hover:bg-red-600 transition-colors shadow-lg hover:scale-110 z-10"
              title="Remove image"
            >
              <X size={16} strokeWidth={3} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center text-gray-400 p-6 text-center">
            <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4 shadow-inner">
              <UploadCloud size={32} className="text-indigo-400" />
            </div>
            <p className="text-base font-semibold text-gray-600">
              Click or drag image to upload
            </p>
            <p className="text-sm text-gray-600 mt-2">
              Supports JPG, PNG, and WebP (max. 5MB)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
