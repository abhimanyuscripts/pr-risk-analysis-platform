import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 5173 is the origin the backend allows (CORS) and returns to after login, so never switch ports silently
  server: { port: 5173, strictPort: true },
})
