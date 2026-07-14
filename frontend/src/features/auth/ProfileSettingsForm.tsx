import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { fetchApi } from "../../lib/api";
import { getAccessToken } from "../../lib/authToken";
import { useAuth } from "./AuthContext";
import { useToast } from "../ui/ToastContext";
import { AvatarUploadDropzone } from "../../components/ui/AvatarUploadDropzone";
import { CoverUploadDropzone } from "../../components/ui/CoverUploadDropzone";
import { useWebPush } from "../../hooks/useWebPush";

const profileSchema = z.object({
  email: z.string().email({ message: "Please enter a valid email address" }),
  password: z
    .string()
    .optional()
    .transform((val) => (val === "" ? undefined : val))
    .refine((val) => !val || val.length >= 8, {
      message: "Password must be at least 8 characters long if provided",
    }),
  bio: z
    .string()
    .max(1500, { message: "Bio cannot exceed 1500 characters" })
    .optional(),
  timezone: z.string(),
  twitter_url: z
    .string()
    .optional()
    .refine(
      (val) =>
        !val ||
        val.startsWith("http://") ||
        val.startsWith("https://") ||
        val === "",
      {
        message: "Please enter a valid URL (starting with http:// or https://)",
      },
    ),
  linkedin_url: z
    .string()
    .optional()
    .refine(
      (val) =>
        !val ||
        val.startsWith("http://") ||
        val.startsWith("https://") ||
        val === "",
      {
        message: "Please enter a valid URL (starting with http:// or https://)",
      },
    ),
  github_url: z
    .string()
    .optional()
    .refine(
      (val) =>
        !val ||
        val.startsWith("http://") ||
        val.startsWith("https://") ||
        val === "",
      {
        message: "Please enter a valid URL (starting with http:// or https://)",
      },
    ),
});

type ProfileFormValues = z.input<typeof profileSchema>;

export function ProfileSettingsForm() {
  const { user, checkUser } = useAuth();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState<File | null>(null);
  const [selectedCover, setSelectedCover] = useState<File | null>(null);

  const { isSupported, isSubscribed, subscribe, unsubscribe } = useWebPush();

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
      bio: user?.bio || "",
      timezone:
        user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
      twitter_url: user?.twitter_url || "",
      linkedin_url: user?.linkedin_url || "",
      github_url: user?.github_url || "",
    },
  });

  useEffect(() => {
    if (user?.email) {
      reset({
        email: user.email,
        password: "",
        bio: user.bio || "",
        timezone:
          user.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
        twitter_url: user.twitter_url || "",
        linkedin_url: user.linkedin_url || "",
        github_url: user.github_url || "",
      });
    }
  }, [user, reset]);

  const onSubmit = async (data: ProfileFormValues) => {
    setLoading(true);

    try {
      let body: FormData | string;

      if (selectedAvatar || selectedCover) {
        const formData = new FormData();
        formData.append("email", data.email);
        if (data.password) formData.append("password", data.password);
        if (data.bio !== undefined) formData.append("bio", data.bio);
        formData.append("timezone", data.timezone);
        formData.append("twitter_url", data.twitter_url || "");
        formData.append("linkedin_url", data.linkedin_url || "");
        formData.append("github_url", data.github_url || "");
        if (selectedAvatar) formData.append("avatar", selectedAvatar);
        if (selectedCover) formData.append("cover_image", selectedCover);
        body = formData;
      } else {
        const payload: Record<string, string> = {
          email: data.email,
          timezone: data.timezone,
          twitter_url: data.twitter_url || "",
          linkedin_url: data.linkedin_url || "",
          github_url: data.github_url || "",
        };
        if (data.password) payload.password = data.password;
        if (data.bio !== undefined) payload.bio = data.bio;
        body = JSON.stringify(payload);
      }

      await fetchApi("/auth/me/", {
        method: "PUT",
        requireAuth: true,
        body: body,
      });

      await checkUser(); 
      addToast("Profile settings updated successfully!", "success");
      reset({
        email: data.email,
        password: "",
        bio: data.bio || "",
        timezone: data.timezone,
        twitter_url: data.twitter_url || "",
        linkedin_url: data.linkedin_url || "",
        github_url: data.github_url || "",
      });
    } catch (err: unknown) {
      addToast(
        err instanceof Error
          ? err.message
          : "Failed to update profile settings.",
        "error",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadData = async () => {
    setDownloading(true);
    try {
      const API_BASE =
        import.meta.env.VITE_API_BASE_URL?.trim() ||
        `${window.location.origin}/api`;
      const token = getAccessToken();
      const response = await fetch(
        `${API_BASE}/auth/me/export/?export_format=csv`,
        {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        },
      );
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `data_export_${user?.username || "data"}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      addToast("Data archive downloaded successfully!", "success");
    } catch {
      addToast("Failed to download data archive.", "error");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <form className="space-y-6 pt-2" onSubmit={handleSubmit(onSubmit)}>
      <CoverUploadDropzone
        currentCoverUrl={user?.cover_image_url}
        onFileSelect={(file) => setSelectedCover(file)}
      />
      <AvatarUploadDropzone
        currentAvatarUrl={user?.avatar_url}
        onFileSelect={(file) => setSelectedAvatar(file)}
      />

      <div className="space-y-2">
        <label
          htmlFor="email"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Email Address
        </label>
        <input
          id="email"
          {...register("email")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.email ? "border-red-500" : ""
          }`}
          type="email"
          placeholder="nerd@homework.com"
          disabled={loading}
        />
        {errors.email && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="bio"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Bio (Markdown Supported)
        </label>
        <textarea
          id="bio"
          {...register("bio")}
          rows={5}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.bio ? "border-red-500" : ""
          }`}
          placeholder="Tell us about yourself... **Bold**, *Italic*, [Links](https://...) are supported!"
          disabled={loading}
        />
        {errors.bio && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.bio.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="password"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          New Password (leave blank to keep current)
        </label>
        <input
          id="password"
          {...register("password")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.password ? "border-red-500" : ""
          }`}
          type="password"
          placeholder="••••••••"
          disabled={loading}
        />
        {errors.password && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.password.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="timezone"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Timezone
        </label>
        <select
          id="timezone"
          {...register("timezone")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card focus:bg-accent ${
            errors.timezone ? "border-red-500" : ""
          }`}
          disabled={loading}
        >
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {(Intl as any).supportedValuesOf("timeZone").map((tz: string) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
        {errors.timezone && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.timezone.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="github_url"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          GitHub URL
        </label>
        <input
          id="github_url"
          {...register("github_url")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.github_url ? "border-red-500" : ""
          }`}
          type="url"
          placeholder="https://github.com/username"
          disabled={loading}
        />
        {errors.github_url && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.github_url.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="linkedin_url"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          LinkedIn URL
        </label>
        <input
          id="linkedin_url"
          {...register("linkedin_url")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.linkedin_url ? "border-red-500" : ""
          }`}
          type="url"
          placeholder="https://linkedin.com/in/username"
          disabled={loading}
        />
        {errors.linkedin_url && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.linkedin_url.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="twitter_url"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Twitter URL
        </label>
        <input
          id="twitter_url"
          {...register("twitter_url")}
          className={`w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card ${
            errors.twitter_url ? "border-red-500" : ""
          }`}
          type="url"
          placeholder="https://twitter.com/username"
          disabled={loading}
        />
        {errors.twitter_url && (
          <p role="alert" className="text-red-600 font-bold ml-2 text-sm">
            {errors.twitter_url.message}
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

        <div className="space-y-2 mt-6">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Browser Notifications
          </label>
          {isSupported ? (
            <button
              type="button"
              onClick={isSubscribed ? unsubscribe : subscribe}
              className={`w-full rounded-2xl border-4 border-black px-5 py-4 font-black text-black text-lg shadow-card-sm transition-all cursor-pointer uppercase flex items-center justify-center gap-2 ${
                isSubscribed
                  ? "bg-red-200 hover:bg-red-300"
                  : "bg-[#E8F0FE] hover:bg-blue-200"
              }`}
            >
              {isSubscribed
                ? "🔕 Disable Notifications"
                : "🔔 Enable Notifications"}
            </button>
          ) : (
            <p className="text-muted ml-2 text-sm italic">
              Push notifications are not supported in this browser.
            </p>
          )}
        </div>

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