import React, { useState, useCallback, useMemo } from "react";
import { Palette, Shuffle, Sliders, Sparkles } from "lucide-react";

import { PaletteDisplay } from "./palette/PaletteDisplay";
import { ContrastChecker } from "./palette/ContrastChecker";
import { ExportPanel } from "./palette/ExportPanel";
import {
  generatePalette,
  randomBaseHue,
  hslToHex,
  type HarmonyType,
} from "./palette/colorUtils";

const HARMONY_OPTIONS: { value: HarmonyType; label: string }[] = [
  { value: "analogous", label: "Analogous" },
  { value: "complementary", label: "Complementary" },
  { value: "triadic", label: "Triadic" },
  { value: "split", label: "Split-Comp." },
  { value: "tetradic", label: "Tetradic" },
];

export function ColorPaletteGenerator() {
  const [baseHue, setBaseHue] = useState(210);
  const [saturation, setSaturation] = useState(72);
  const [lightness, setLightness] = useState(50);
  const [count, setCount] = useState(5);
  const [harmony, setHarmony] = useState<HarmonyType>("analogous");
  const [paletteName, setPaletteName] = useState("my-palette");
  const [showShades, setShowShades] = useState(true);
  const [selectedFg, setSelectedFg] = useState("#1f1c18");
  const [selectedBg, setSelectedBg] = useState("#ffffff");
  const [showExport, setShowExport] = useState(false);

  const colors = useMemo(
    () => generatePalette(baseHue, saturation, lightness, count, harmony),
    [baseHue, saturation, lightness, count, harmony],
  );

  const randomize = useCallback(() => {
    setBaseHue(randomBaseHue());
    setSaturation(50 + Math.floor(Math.random() * 40));
    setLightness(35 + Math.floor(Math.random() * 30));
    setCount(3 + Math.floor(Math.random() * 5));
  }, []);

  const selectColorForContrast = useCallback(
    (hex: string) => {
      if (selectedFg === hex) return;
      setSelectedBg(selectedFg);
      setSelectedFg(hex);
    },
    [selectedFg],
  );

  const swapContrastColors = useCallback(() => {
    setSelectedFg(selectedBg);
    setSelectedBg(selectedFg);
  }, [selectedFg, selectedBg]);

  const basePreviewHex = hslToHex(baseHue, saturation, lightness);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <Palette className="w-3.5 h-3.5" /> Developer Tool
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2]">
            Color Palette Generator
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-xl">
            Generate accessible color palettes with WCAG contrast checking.
            Export as CSS variables, SCSS, JSON, or Tailwind config.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl shadow-card-sm self-start md:self-auto">
          <div
            className="w-12 h-12 rounded-xl border-2 border-black"
            style={{ backgroundColor: basePreviewHex }}
          />
          <div>
            <div className="text-[10px] font-black uppercase text-muted tracking-wider">Base</div>
            <div className="text-sm font-mono font-black text-text dark:text-[#f0ebe2] uppercase">
              {basePreviewHex}
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
        <div className="flex items-center justify-between px-4 py-3 border-b-4 border-black dark:border-[#2e2924]">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-primary" />
            <span className="font-black text-xs uppercase tracking-wider text-text dark:text-[#f0ebe2]">
              Palette Controls
            </span>
          </div>
          <button
            onClick={randomize}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-black uppercase bg-primary text-black border-2 border-black rounded-lg hover:-translate-y-0.5 transition-all"
          >
            <Shuffle className="w-3 h-3" /> Randomize
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Base Hue */}
          <div>
            <label className="flex items-center justify-between text-[10px] font-black uppercase text-muted dark:text-[#9b8f80] mb-1.5">
              <span>Base Hue</span>
              <span className="font-mono text-text dark:text-[#f0ebe2]">{baseHue}°</span>
            </label>
            <input
              type="range"
              min={0}
              max={359}
              value={baseHue}
              onChange={(e) => setBaseHue(Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none bg-gradient-to-r from-red-500 via-green-500 via-blue-500 to-red-500 cursor-pointer accent-primary"
            />
          </div>

          {/* Saturation */}
          <div>
            <label className="flex items-center justify-between text-[10px] font-black uppercase text-muted dark:text-[#9b8f80] mb-1.5">
              <span>Saturation</span>
              <span className="font-mono text-text dark:text-[#f0ebe2]">{saturation}%</span>
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={saturation}
              onChange={(e) => setSaturation(Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none bg-gradient-to-r from-gray-400 to-vivid cursor-pointer accent-primary"
            />
          </div>

          {/* Lightness */}
          <div>
            <label className="flex items-center justify-between text-[10px] font-black uppercase text-muted dark:text-[#9b8f80] mb-1.5">
              <span>Lightness</span>
              <span className="font-mono text-text dark:text-[#f0ebe2]">{lightness}%</span>
            </label>
            <input
              type="range"
              min={10}
              max={90}
              value={lightness}
              onChange={(e) => setLightness(Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none bg-gradient-to-r from-black to-white cursor-pointer accent-primary"
            />
          </div>

          {/* Color Count */}
          <div>
            <label className="flex items-center justify-between text-[10px] font-black uppercase text-muted dark:text-[#9b8f80] mb-1.5">
              <span>Colors</span>
              <span className="font-mono text-text dark:text-[#f0ebe2]">{count}</span>
            </label>
            <input
              type="range"
              min={2}
              max={10}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none bg-primary/30 cursor-pointer accent-primary"
            />
          </div>

          {/* Harmony */}
          <div>
            <label className="text-[10px] font-black uppercase text-muted dark:text-[#9b8f80] mb-1.5 block">
              Color Harmony
            </label>
            <div className="flex flex-wrap gap-1">
              {HARMONY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setHarmony(opt.value)}
                  className={`px-2.5 py-1 text-[10px] font-black rounded-lg border-2 transition-all ${
                    harmony === opt.value
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-white dark:bg-[#1f1c18] text-muted dark:text-[#c4bbae] border-black/15 dark:border-[#2e2924] hover:border-black dark:hover:border-[#c4bbae]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Palette Name */}
          <div>
            <label className="text-[10px] font-black uppercase text-muted dark:text-[#9b8f80] mb-1.5 block">
              Palette Name
            </label>
            <input
              type="text"
              value={paletteName}
              onChange={(e) => setPaletteName(e.target.value)}
              className="w-full px-3 py-2 font-mono text-xs font-bold text-text dark:text-[#f0ebe2] bg-white dark:bg-[#0f0e0c] border-2 border-black dark:border-[#2e2924] rounded-lg outline-none focus:border-primary transition-colors"
              spellCheck={false}
            />
          </div>
        </div>
      </div>

      {/* Palette Display */}
      <PaletteDisplay
        colors={colors}
        showShades={showShades}
        onToggleShades={() => setShowShades((p) => !p)}
        onSelectColor={selectColorForContrast}
        selectedHex={selectedFg}
      />

      {/* Bottom row: Contrast + Export */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ContrastChecker
          foreground={selectedFg}
          background={selectedBg}
          onSwap={swapContrastColors}
        />

        <div>
          {!showExport ? (
            <button
              onClick={() => setShowExport(true)}
              className="w-full h-full min-h-[200px] bg-surface-low dark:bg-[#151411] border-4 border-dashed border-black/20 dark:border-[#2e2924] rounded-2xl flex flex-col items-center justify-center gap-3 hover:border-primary hover:bg-primary/5 transition-all cursor-pointer"
            >
              <Sparkles className="w-8 h-8 text-primary animate-pulse" />
              <span className="font-black text-sm text-muted dark:text-[#c4bbae]">
                Click to Export Palette
              </span>
              <span className="text-[10px] font-bold text-muted/60 dark:text-[#9b8f80]/60">
                CSS, SCSS, JSON, or Tailwind config
              </span>
            </button>
          ) : (
            <ExportPanel colors={colors} paletteName={paletteName} />
          )}
        </div>
      </div>
    </div>
  );
}

export default ColorPaletteGenerator;
