import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Entwicklung: `npm run dev` (Port 5173) leitet /api an den Python-Server weiter.
// Produktion: `npm run build` schreibt nach dist/, das main.py ausliefert.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.HIPPOKRATES_API ?? "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 900 },
});
