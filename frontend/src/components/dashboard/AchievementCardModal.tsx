import React, { useRef, useEffect } from "react";
import { Download, Share2, X } from "lucide-react";
import type { PersonalStats } from "./types";

interface AchievementCardModalProps {
  isOpen: boolean;
  onClose: () => void;
  personalStats: PersonalStats;
  username: string;
}

export function AchievementCardModal({
  isOpen,
  onClose,
  personalStats,
  username,
}: AchievementCardModalProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!isOpen || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set high-res canvas for crisp text
    const scale = 2; // For retina displays
    canvas.width = 800 * scale;
    canvas.height = 450 * scale;

    // Scale context
    ctx.scale(scale, scale);

    // Helper for drawing neo-brutalist boxes
    const drawBox = (
      x: number,
      y: number,
      w: number,
      h: number,
      bg: string,
      shadowOffset = 6,
    ) => {
      // Shadow
      ctx.fillStyle = "#000000";
      ctx.fillRect(x + shadowOffset, y + shadowOffset, w, h);
      // Box
      ctx.fillStyle = bg;
      ctx.fillRect(x, y, w, h);
      // Border
      ctx.lineWidth = 4;
      ctx.strokeStyle = "#000000";
      ctx.strokeRect(x, y, w, h);
    };

    // Background
    ctx.fillStyle = "#f0ebe2"; // Off-white
    ctx.fillRect(0, 0, 800, 450);

    // Main Border
    ctx.lineWidth = 12;
    ctx.strokeStyle = "#000000";
    ctx.strokeRect(6, 6, 800 - 12, 450 - 12);

    // Decorative shapes
    drawBox(650, 40, 100, 100, "#FFEBC2"); // Yellow box
    drawBox(700, 90, 60, 60, "#c3c0ff"); // Purple box

    // Header text
    ctx.fillStyle = "#000000";
    ctx.font = "900 48px sans-serif";
    ctx.fillText("ATELIER CONTRIBUTOR", 50, 100);

    // Username
    ctx.font = "800 32px sans-serif";
    ctx.fillStyle = "#ff3b30"; // Primary red
    ctx.fillText(`@${username}`, 50, 150);

    // Stats Grid
    const statBox = (
      x: number,
      y: number,
      label: string,
      value: string,
      color: string,
    ) => {
      drawBox(x, y, 150, 120, color);

      ctx.fillStyle = "#000000";
      ctx.font = "800 16px sans-serif";
      ctx.fillText(label.toUpperCase(), x + 20, y + 40);

      ctx.font = "900 42px sans-serif";
      ctx.fillText(value, x + 20, y + 90);
    };

    statBox(50, 220, "Rank", `#${personalStats.rank}`, "#FFFFFF");
    statBox(220, 220, "XP", `${personalStats.total_xp}`, "#FFEBC2");
    statBox(390, 220, "PRs Merged", `${personalStats.prs_merged}`, "#c3c0ff");
    statBox(560, 220, "Streak", `${personalStats.streak_days}`, "#FFFFFF");

    // Footer
    ctx.fillStyle = "#000000";
    ctx.font = "700 16px sans-serif";
    ctx.fillText(
      "Join the Open Source Atelier - github.com/diksha78dev/Open-Source-Contribution-Atelier",
      50,
      400,
    );
  }, [isOpen, personalStats, username]);

  const downloadImage = () => {
    if (!canvasRef.current) return;
    const link = document.createElement("a");
    link.download = `atelier-achievement-${username}.png`;
    link.href = canvasRef.current.toDataURL("image/png");
    link.click();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#1a1a1a] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden max-w-4xl w-full flex flex-col relative shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 bg-red-400 border-2 border-black rounded-full hover:bg-red-500 transition-colors z-10"
        >
          <X size={20} className="text-black" />
        </button>
        <div className="p-8 flex flex-col items-center gap-6">
          <h2 className="text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-3">
            <Share2 className="text-primary" size={32} />
            Share Your Achievement
          </h2>
          <canvas
            ref={canvasRef}
            style={{ width: "100%", maxWidth: "800px" }}
            className="border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] bg-white"
          />
          <div className="flex gap-4">
            <button
              onClick={downloadImage}
              className="flex items-center gap-2 px-8 py-4 bg-primary text-black font-black text-xl border-4 border-black rounded-2xl hover:-translate-y-1 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-all"
            >
              <Download size={24} />
              Download Card
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
