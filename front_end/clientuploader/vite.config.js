import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        widget: path.resolve(__dirname, 'chat-widget.html'),
        iframe: path.resolve(__dirname, 'widget.html'), // ✅ widget.html IFRAME embebido
      },
    },
  },
});
