import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    watch: {
      ignored: [
        "**/build/**",
        "**/backend/dist/**",
        "**/installer/**",
        "**/.venv/**",
        "**/test-results/**",
      ],
    },
  },
  build: {
    outDir: "renderer",
  },
});
