import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { fetchApi } from "../../lib/api";
import { useAuth } from "./AuthContext";
import { useToast } from "../ui/ToastContext";
import { AvatarUploadDropzone } from "../../components/ui/AvatarUploadDropzone";

const profileSchema = z.object({
  email: z.string().email({ message: "Please enter a valid email address" }),
  password: z
    .string()
    .optional()
    .transform((val) => (val === "" ? undefined : val))
    .refine((val) => !val || val.length >= 8, {
      message: "Password must be at least 8 characters long if provided",
    }),
});

type ProfileFormValues = z.input<typeof profileSchema>;

export function ProfileSettingsForm() {
  const { user, checkUser } = useAuth();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState<File | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      email: user?.email || "",
      password: "",
    },
  });

  useEffect(() => {
    if (user?.email) {
      reset({ email: user.email, password: "" });
    }
  }, [user, reset]);

  const onSubmit = async (data: ProfileFormValues) => {
    setLoading(true);

    try {
      let body: FormData | string;
      
      // If we have a file, we MUST use FormData
      if (selectedAvatar) {
        const formData = new FormData();
        formData.append("email", data.email);
        if (data.password) {
          formData.append("password", data.password);
        }
        formData.append("avatar", selectedAvatar);
        body = formData;
      } else {
        // Fallback to JSON payload if no file is selected (cleaner for simple updates)
        const payload: Record<string, string> = { email: data.email };
        if (data.password) {
          payload.password = data.password;
        }
        body = JSON.stringify(payload);
      }

      await fetchApi("/auth/me/", {
        method: "PUT",
        requireAuth: true,
        body: body,
      });
      
      await checkUser(); // Refresh global user context to show new avatar instantly
      addToast("Profile settings updated successfully!", "success");
      reset({ email: data.email, password: "" });
    } catch (err: unknown) {
      addToast(
        err instanceof Error ? err.message : "Failed to update profile settings.",
        "error"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadData = async () => {
    setDownloading(true);
    try {
      const blob = await fetchApi("/auth/me/export/?export_format=csv", {
        requireAuth: true,
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(blob as Blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `data_export_${user?.username || "data"}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      addToast("Data archive downloaded successfully!", "success");
    } catch (err: unknown) {
      addToast("Failed to download data archive.", "error");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <form className="space-y-6 pt-2" onSubmit={handleSubmit(onSubmit)}>
      <AvatarUploadDropzone
        currentAvatarUrl={user?.avatar_url}
        onFileSelect={(file) => setSelectedAvatar(file)}
      />

      <div className="space-y-2">
        <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
          Email Address
        </label>
        <input
          {...register("email")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.email ? "border-red-500" : ""
          }`}
          type="email"
          placeholder="nerd@homework.com"
          disabled={loading}
        />
        {errors.email && (
          <p className="text-red-600 font-bold ml-2 text-sm">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
          New Password (leave blank to keep current)
        </label>
        <input
          {...register("password")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.password ? "border-red-500" : ""
          }`}
          type="password"
          placeholder="••••••••"
          disabled={loading}
        />
        {errors.password && (
          <p className="text-red-600 font-bold ml-2 text-sm">
            {errors.password.message}
          </p>
        )}
      </div>

    <div className="space-y-4 mt-8">
        <button
          className="w-full rounded-2xl border-4 border-black bg-accent px-5 py-5 font-black text-black text-xl shadow-card hover:bg-tertiary transition-colors cursor-pointer uppercase disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Updating..." : "Save Settings"}
        </button>

        <hr className="border-2 border-black/10 my-8" />

        <div className="space-y-2">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Data Privacy (GDPR)
          </label>
          <button
            type="button"
            onClick={handleDownloadData}
            disabled={downloading}
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 font-black text-black text-lg shadow-card-sm hover:-translate-y-1 hover:shadow-card transition-all cursor-pointer uppercase disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {downloading ? "Compiling Archive..." : "Download All My Data"}
          </button>
        </div>
      </div>
    </form>
  );
}
