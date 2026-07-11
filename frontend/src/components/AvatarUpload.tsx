import React, { useState, useRef } from "react";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import "./AvatarUpload.css";

interface AvatarUploadProps {
  currentAvatar?: string | null;
  onAvatarUpdate: (url: string) => void;
}

export function AvatarUpload({
  currentAvatar,
  onAvatarUpdate,
}: AvatarUploadProps) {
  const [preview, setPreview] = useState<string | null>(currentAvatar || null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (file: File) => {
    const validTypes = ["image/jpeg", "image/png", "image/gif", "image/webp"];
    if (!validTypes.includes(file.type)) {
      setError("Please upload a JPEG, PNG, GIF, or WebP image.");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("Image size must be under 5MB.");
      return;
    }

    setError(null);
    setIsUploading(true);

    const reader = new FileReader();
    reader.onload = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);

    const formData = new FormData();
    formData.append("avatar", file);

    try {
      const response = await fetchApi("/accounts/profile/avatar/", {
        method: "POST",
        body: formData,
      });

      if (response.avatar_url) {
        onAvatarUpdate(response.avatar_url);
      }
    } catch (err) {
      setError("Failed to upload image. Please try again.");
      setPreview(currentAvatar || null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemove = async () => {
    try {
      await fetchApi("/accounts/profile/avatar/", {
        method: "DELETE",
      });
      setPreview(null);
      onAvatarUpdate("");
    } catch (err) {
      setError("Failed to remove avatar.");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  return (
    <div className="avatar-upload-container">
      <div
        className={`avatar-preview ${isDragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        {preview ? (
          <img src={preview} alt="Avatar preview" className="avatar-image" />
        ) : (
          <div className="avatar-placeholder">
            <span className="avatar-icon">📷</span>
            <span className="avatar-text">Click or drag to upload</span>
          </div>
        )}
        {isUploading && (
          <div className="upload-spinner">
            <div className="spinner"></div>
          </div>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelect(file);
        }}
        className="file-input-hidden"
      />

      {error && <p className="avatar-error">{error}</p>}

      <div className="avatar-actions">
        <button
          className="avatar-btn upload"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? "Uploading..." : "📤 Upload"}
        </button>
        {preview && (
          <button
            className="avatar-btn remove"
            onClick={handleRemove}
            disabled={isUploading}
          >
            🗑️ Remove
          </button>
        )}
      </div>
    </div>
  );
}
