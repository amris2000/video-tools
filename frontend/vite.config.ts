import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,

    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },

      "/media": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },

      "/renders": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },

      "/social-renders": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "../build/frontend",
    emptyOutDir: true,
  },
});
