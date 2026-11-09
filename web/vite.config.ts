import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: `npm run dev` proxies /api to the FastAPI server on :5050.
// Prod: `npm run build` -> web/dist, served by FastAPI from the same origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:5050' },
  },
})
