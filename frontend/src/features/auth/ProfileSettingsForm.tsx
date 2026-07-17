import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { fetchApi } from "../../lib/api";
import { useAuth } from "./AuthContext";
import { useToast } from "../ui/ToastContext";
import { AvatarUploadDropzone } from "../../components/ui/AvatarUploadDropzone";
import { CoverUploadDropzone } from "../../components/ui/CoverUploadDropzone";
import { useWebPush } from "../../hooks/useWebPush";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { UnsavedChangesDialog } from "../../components/ui/UnsavedChangesDialog";

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
  receive_weekly_digest: z.boolean().default(true),
});

type ProfileFormValues = z.input<typeof profileSchema>;

interface ProfileSettingsFormProps {
  onChange?: (values: ProfileFormValues) => void;
}


export function ProfileSettingsForm({ onChange }: ProfileSettingsFormProps) {
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
  watch,
  formState: { errors, isDirty },
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
      receive_weekly_digest: user?.receive_weekly_digest ?? true,
    },
  });

    const hasUnsavedChanges =
  isDirty || selectedAvatar !== null || selectedCover !== null;

const unsavedChanges = useUnsavedChanges({
  isDirty: hasUnsavedChanges,
  message:
    "Your profile changes have not been saved. Discard them and leave this page?",
  onDiscard: () => {
    setSelectedAvatar(null);
    setSelectedCover(null);
  },
});

  const watchedValues = watch();

  useEffect(() => {
    onChange?.({
      ...watchedValues,
      avatarFile: selectedAvatar,
      coverFile: selectedCover,
    });
  }, [watchedValues, selectedAvatar, selectedCover, onChange]);

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
        receive_weekly_digest: user.receive_weekly_digest ?? true,
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
        formData.append(
          "receive_weekly_digest",
          String(data.receive_weekly_digest),
        );
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
          receive_weekly_digest: String(data.receive_weekly_digest),
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
        receive_weekly_digest: data.receive_weekly_digest,
      });
      setSelectedAvatar(null);
      setSelectedCover(null);
    } catch (error: unknown) {
  const message =
    error instanceof Error
      ? error.message
      : "Failed to update profile settings.";

  addToast(message, "error");
}
 finally {
      setLoading(false);
    }
  };

  const handleDownloadData = async () => {
    setDownloading(true);
    try {
      const API_BASE =
        import.meta.env.VITE_API_BASE_URL?.trim() ||
        `${window.location.origin}/api`;
      const token = localStorage.getItem("accessToken");
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
     <>
    <form className="space-y-6 pt-2" onSubmit={handleSubmit(onSubmit)}>
      <AvatarUploadDropzone
        currentAvatarUrl={user?.avatar_url}
        onFileSelect={(file) => setSelectedAvatar(file)}
      />

      <CoverUploadDropzone
        currentCoverUrl={user?.cover_image_url}
        onFileSelect={(file) => setSelectedCover(file)}
      />

      <div className="space-y-1.5">
        <label
          htmlFor="email"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          Email Address
        </label>
        <input
          id="email"
          {...register("email")}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none placeholder:text-muted/60 focus:bg-accent shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm ${
            errors.email ? "border-red-500" : ""
          }`}
          type="email"
          placeholder="nerd@homework.com"
          disabled={loading}
        />
        {errors.email && (
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="bio"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          Bio (Markdown Supported)
        </label>
        <textarea
          id="bio"
          {...register("bio")}
          rows={4}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none placeholder:text-muted/60 focus:bg-accent shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm ${
            errors.bio ? "border-red-500" : ""
          }`}
          placeholder="Tell us about yourself... **Bold**, *Italic*, [Links](https://...) are supported!"
          disabled={loading}
        />
        {errors.bio && (
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.bio.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="password"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          New Password (leave blank to keep current)
        </label>
        <input
          id="password"
          {...register("password")}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm ${
            errors.password ? "border-red-500" : ""
          }`}
          type="password"
          placeholder="••••••••"
          disabled={loading}
        />
        {errors.password && (
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.password.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="timezone"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          Timezone
        </label>
        <select
          id="timezone"
          {...register("timezone")}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm focus:bg-accent ${
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
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.timezone.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="github_url"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          GitHub URL
        </label>
        <input
          id="github_url"
          {...register("github_url")}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none placeholder:text-muted/60 focus:bg-accent shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm ${
            errors.github_url ? "border-red-500" : ""
          }`}
          type="url"
          placeholder="https://github.com/username"
          disabled={loading}
        />
        {errors.github_url && (
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.github_url.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="linkedin_url"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          LinkedIn URL
        </label>
        <input
          id="linkedin_url"
          {...register("linkedin_url")}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none placeholder:text-muted/60 focus:bg-accent shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm ${
            errors.linkedin_url ? "border-red-500" : ""
          }`}
          type="url"
          placeholder="https://linkedin.com/in/username"
          disabled={loading}
        />
        {errors.linkedin_url && (
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.linkedin_url.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="twitter_url"
          className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs"
        >
          Twitter URL
        </label>
        <input
          id="twitter_url"
          {...register("twitter_url")}
          className={`w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 text-black font-bold text-sm outline-none placeholder:text-muted/60 focus:bg-accent shadow-sm transition-all focus:-translate-y-0.5 focus:shadow-card-sm ${
            errors.twitter_url ? "border-red-500" : ""
          }`}
          type="url"
          placeholder="https://twitter.com/username"
          disabled={loading}
        />
        {errors.twitter_url && (
          <p role="alert" className="text-red-600 font-bold ml-1.5 text-xs">
            {errors.twitter_url.message}
          </p>
        )}
      </div>

      <div className="space-y-4 mt-6">
        <button
          className="w-full rounded-xl border-2 border-black bg-accent px-4 py-3 font-bold text-black text-sm shadow-card-sm hover:bg-tertiary transition-colors cursor-pointer uppercase disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Updating..." : "Save Settings"}
        </button>

        <div className="space-y-1.5 mt-4">
          <label className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs">
            Browser Notifications
          </label>
          {isSupported ? (
            <button
              type="button"
              onClick={isSubscribed ? unsubscribe : subscribe}
              className={`w-full rounded-xl border-2 border-black px-4 py-2.5 font-bold text-black text-sm shadow-card-sm transition-all cursor-pointer uppercase flex items-center justify-center gap-2 ${
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
            <p className="text-muted ml-1.5 text-xs italic">
              Push notifications are not supported in this browser.
            </p>
          )}
        </div>

        <hr className="border border-black/10 my-6" />

        <div className="space-y-1.5">
          <label className="font-bold text-black ml-1.5 uppercase tracking-wide text-xs">
            Data Privacy (GDPR)
          </label>
          <button
            type="button"
            onClick={handleDownloadData}
            disabled={downloading}
            className="w-full rounded-xl border-2 border-black bg-white px-4 py-2.5 font-bold text-black text-sm shadow-card-sm hover:-translate-y-0.5 hover:shadow-card-sm transition-all cursor-pointer uppercase disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {downloading ? "Compiling Archive..." : "Download All My Data"}
          </button>
        </div>
      </div>
    </form>

    <UnsavedChangesDialog
      open={unsavedChanges.isBlocked}
      message={unsavedChanges.message}
      onStay={unsavedChanges.stay}
      onDiscard={unsavedChanges.discard}
    />
    </>
  );
}
