import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend (backend/main.py) runs on :8000 (override with API_PORT).
// Proxy API and image requests so the frontend can use relative URLs like
// /api/products, and so the session cookie stays same-origin.
const api = `http://127.0.0.1:${process.env.API_PORT ?? '8000'}`

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': api,
      '/media': api,
    },
  },
})
