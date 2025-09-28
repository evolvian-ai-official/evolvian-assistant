import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  base: "/", // 👈 rutas absolutas en prod
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),   // Admin
        widget: resolve(__dirname, "widget.html") // Widget iframe 👈 añadido
      },
    },
  },
  server: {
    port: 4223,
  },
});
