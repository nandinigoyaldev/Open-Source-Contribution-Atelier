import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/minimal-setup.ts"],
    include: ["src/components/ui/skeletons/**/*.test.tsx"],
    globals: true,
  },
});
