import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 构建产物直接输出到后端的静态目录，这样 `python run.py` 起一个进程即可同时
// 提供 API 与前端页面，无需额外的 nginx 或跨域配置。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../llm_backend/static/dist',
    emptyOutDir: true,
    assetsDir: 'assets',
    chunkSizeWarningLimit: 1500,
  },
  server: {
    port: 5173,
    // 开发模式下把接口代理到后端，避免浏览器跨域
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/chat-rag': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
