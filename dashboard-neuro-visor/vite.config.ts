import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND_PORT = parseInt(process.env.BIORAG_DASHBOARD_BACKEND_PORT || '8001', 10)
const FRONTEND_PORT = parseInt(process.env.BIORAG_DASHBOARD_FRONTEND_PORT || '3000', 10)

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    proxy: {
      '/api': {
        target: `http://localhost:${BACKEND_PORT}`,
        changeOrigin: true,
      },
    },
  },
})
