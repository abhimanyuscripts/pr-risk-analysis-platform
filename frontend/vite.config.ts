import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 5173 is the origin the backend returns to after login, so never switch ports silently.
  // /api goes to the FastAPI backend, so the app uses the same relative paths here as in production.
  server: { port: 5173, strictPort: true, proxy: { '/api': 'http://localhost:8000' } },
  preview: { port: 5173, strictPort: true, proxy: { '/api': 'http://localhost:8000' } },
})
