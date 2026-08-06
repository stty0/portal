import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// 개발 서버는 /api 를 Traefik(9443)으로 넘긴다. 배포 시에는 같은 도메인이라
// 프록시가 필요 없다 — Traefik이 /api 를 백엔드로 라우팅한다.
const API_TARGET = process.env.VITE_API_TARGET ?? 'https://192.168.1.100:9443'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    // noVNC 1.7이 top-level await를 쓴다(WebCodecs H.264 지원 감지). 기본 타깃(es2020)은
    // 이를 지원하지 않아 빌드가 실패한다. es2022는 Chrome 89+·Firefox 89+·Safari 15+.
    target: 'es2022',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        secure: false, // 개발 프록시 — 사설 IP로 붙어 SNI가 맞지 않는다
        headers: { Host: 'www.dt-hpc.net' },
      },
    },
  },
})
