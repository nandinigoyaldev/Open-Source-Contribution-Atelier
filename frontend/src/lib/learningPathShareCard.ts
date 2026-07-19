/**
 * Learning Path share card — pure helpers for SVG/PNG export.
 * Uses progress stats (modules, streak, badges); no certificate dependency.
 */

export interface LearningPathShareStats {
  username: string;
  modulesCompleted: number;
  modulesTotal: number;
  streakDays: number;
  badgeCount: number;
  /** 0–100 overall lesson/module completion hint */
  completionPercent: number;
}

export function computeShareStats(input: {
  username?: string | null;
  modules?: Array<{
    status: string;
    lessons_count?: number;
    completed_lessons_count?: number;
  }>;
  streakDays?: number | null;
  badgeCount?: number | null;
}): LearningPathShareStats {
  const modules = input.modules ?? [];
  const modulesTotal = modules.length;
  const modulesCompleted = modules.filter(
    (m) => m.status === "completed",
  ).length;

  let lessonsTotal = 0;
  let lessonsDone = 0;
  for (const m of modules) {
    lessonsTotal += m.lessons_count ?? 0;
    lessonsDone += m.completed_lessons_count ?? 0;
  }

  const completionPercent =
    lessonsTotal > 0
      ? Math.round((lessonsDone / lessonsTotal) * 100)
      : modulesTotal > 0
        ? Math.round((modulesCompleted / modulesTotal) * 100)
        : 0;

  return {
    username: (input.username || "learner").replace(/^@/, ""),
    modulesCompleted,
    modulesTotal,
    streakDays: Math.max(0, input.streakDays ?? 0),
    badgeCount: Math.max(0, input.badgeCount ?? 0),
    completionPercent,
  };
}

/** True when the learner has something meaningful to share. */
export function hasShareableProgress(stats: LearningPathShareStats): boolean {
  return (
    stats.modulesCompleted > 0 ||
    stats.streakDays > 0 ||
    stats.badgeCount > 0 ||
    stats.completionPercent > 0
  );
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Build a neobrutalist SVG progress card (1200×630 — social-friendly). */
export function buildLearningPathShareSvg(
  stats: LearningPathShareStats,
  options?: { generatedAt?: Date },
): string {
  const date = (options?.generatedAt ?? new Date()).toLocaleDateString(
    "en-US",
    {
      year: "numeric",
      month: "short",
      day: "numeric",
    },
  );
  const user = escapeXml(`@${stats.username}`);
  const barWidth = Math.max(0, Math.min(100, stats.completionPercent)) * 7.2; // max 720

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="Learning path progress for ${user}">
  <rect width="1200" height="630" fill="#FFF8EF"/>
  <rect x="24" y="24" width="1152" height="582" fill="#FFFFFF" stroke="#111111" stroke-width="8"/>
  <rect x="40" y="40" width="1120" height="550" fill="none" stroke="#111111" stroke-width="3" stroke-dasharray="10 8"/>

  <rect x="64" y="72" width="220" height="40" fill="#FFE066" stroke="#111111" stroke-width="4"/>
  <text x="74" y="98" font-family="Arial Black, Arial, sans-serif" font-size="16" font-weight="900" fill="#111111">LEARNING PATH</text>

  <text x="64" y="170" font-family="Arial Black, Arial, sans-serif" font-size="48" font-weight="900" fill="#111111">Open Source Atelier</text>
  <text x="64" y="220" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#FF3B30">${user}</text>
  <text x="64" y="260" font-family="Arial, sans-serif" font-size="18" font-weight="600" fill="#555555">Progress snapshot · ${escapeXml(date)}</text>

  <rect x="64" y="300" width="240" height="140" fill="#C3C0FF" stroke="#111111" stroke-width="5"/>
  <text x="84" y="340" font-family="Arial, sans-serif" font-size="16" font-weight="800" fill="#111111">MODULES</text>
  <text x="84" y="400" font-family="Arial Black, Arial, sans-serif" font-size="48" font-weight="900" fill="#111111">${stats.modulesCompleted}/${stats.modulesTotal || 0}</text>

  <rect x="334" y="300" width="240" height="140" fill="#FFEBC2" stroke="#111111" stroke-width="5"/>
  <text x="354" y="340" font-family="Arial, sans-serif" font-size="16" font-weight="800" fill="#111111">STREAK</text>
  <text x="354" y="400" font-family="Arial Black, Arial, sans-serif" font-size="48" font-weight="900" fill="#111111">${stats.streakDays}d</text>

  <rect x="604" y="300" width="240" height="140" fill="#B8F2E6" stroke="#111111" stroke-width="5"/>
  <text x="624" y="340" font-family="Arial, sans-serif" font-size="16" font-weight="800" fill="#111111">BADGES</text>
  <text x="624" y="400" font-family="Arial Black, Arial, sans-serif" font-size="48" font-weight="900" fill="#111111">${stats.badgeCount}</text>

  <rect x="874" y="300" width="240" height="140" fill="#FFD6E0" stroke="#111111" stroke-width="5"/>
  <text x="894" y="340" font-family="Arial, sans-serif" font-size="16" font-weight="800" fill="#111111">COMPLETE</text>
  <text x="894" y="400" font-family="Arial Black, Arial, sans-serif" font-size="48" font-weight="900" fill="#111111">${stats.completionPercent}%</text>

  <text x="64" y="490" font-family="Arial, sans-serif" font-size="16" font-weight="800" fill="#111111">OVERALL PROGRESS</text>
  <rect x="64" y="510" width="720" height="28" fill="#F0EBE2" stroke="#111111" stroke-width="4"/>
  <rect x="64" y="510" width="${barWidth}" height="28" fill="#22C55E" stroke="#111111" stroke-width="4"/>

  <text x="64" y="580" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#666666">Not a certificate — share your learning-path momentum ✨</text>
</svg>`;
}

export function downloadTextFile(
  filename: string,
  contents: string,
  mime: string,
): void {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadSvgFile(
  stats: LearningPathShareStats,
  svg = buildLearningPathShareSvg(stats),
): void {
  downloadTextFile(
    `atelier-learning-path-${stats.username}.svg`,
    svg,
    "image/svg+xml;charset=utf-8",
  );
}

/** Rasterize SVG → PNG via canvas (client-side, no extra deps). */
export function downloadPngFromSvg(
  stats: LearningPathShareStats,
  svg = buildLearningPathShareSvg(stats),
): Promise<void> {
  return new Promise((resolve, reject) => {
    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 1200;
        canvas.height = 630;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          URL.revokeObjectURL(url);
          reject(new Error("Canvas unsupported"));
          return;
        }
        ctx.fillStyle = "#FFF8EF";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        const link = document.createElement("a");
        link.download = `atelier-learning-path-${stats.username}.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
        resolve();
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load SVG for PNG export"));
    };
    img.src = url;
  });
}
