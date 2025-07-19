import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        widget: path.resolve(__dirname, 'chat-widget.html'),
        iframe: path.resolve(__dirname, 'widget.html'),
      },
      output: {
        entryFileNames: (chunk) => {
          return chunk.name === 'widget' ? 'assets/widget-app.js' : 'assets/[name].js';
        },
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8001",
    },
  },
});
