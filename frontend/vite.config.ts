import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // PLARNO_API lets you point the dev server at a backend on another port (default: the README's port 8000)
  server: { port: 5173, proxy: { '/api': process.env.PLARNO_API ?? 'http://127.0.0.1:8000' } },
  build: { chunkSizeWarningLimit: 1200, rollupOptions: { output: { manualChunks: { three: ['three', '@react-three/fiber', '@react-three/drei'], map: ['maplibre-gl'], motion: ['framer-motion'] } } } },
})
