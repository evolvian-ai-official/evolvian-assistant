import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  base: "./",
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),   // Admin
        widget: resolve(__dirname, "widget.html") // Widget iframe
      },
    },
    assetsDir: "assets",
  },
  server: {
    port: 4223, // ⚡ fija el puerto del frontend para evitar cambios
  },
});
