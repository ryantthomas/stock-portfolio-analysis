import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Shared by the dev server and `vite preview`.
const API_PROXY = {
  "/api": {
    target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend so the browser sees one origin
    // in development and CORS never enters the picture.
    proxy: API_PROXY,
  },
  // The same proxy for `vite preview`, so a production build can be exercised
  // against a local API exactly as the dev server is.
  preview: {
    port: 4173,
    proxy: API_PROXY,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        // Charting is by far the heaviest dependency and changes far less
        // often than app code, so it gets its own long-lived cache entry.
        manualChunks: {
          charts: ["recharts"],
          react: ["react", "react-dom"],
        },
      },
    },
  },
});
