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
    // ⚡ Usa "dist" para despliegues de frontend SaaS (Render)
    //outDir: "dist",

    // ⚡ Usa "../../static" cuando quieras regenerar el widget servido por FastAPI
    outDir: "../../static",

    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),   // Admin panel
        widget: resolve(__dirname, "widget.html") // Widget iframe
      },
    },
  },

  server: {
    port: 4223,       // Siempre usar 4223
    strictPort: true, // No usar otro puerto si está ocupado → fallo visible
    host: true,       // Siempre mostrar la URL en terminal
    open: false,      // No abrir navegador automático
  },
});
