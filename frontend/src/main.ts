import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import { useClusterStore } from './stores/cluster'
import { getToken } from './api/client'
import './assets/main.css'

async function bootstrap() {
  const app = createApp(App)
  app.use(createPinia())

  // 라우터 가드가 돌기 전에 세션을 복구해 둔다 — 새로고침 시 로그인 화면이 깜빡이지 않도록.
  if (getToken()) {
    const auth = useAuthStore()
    await auth.restore()
    if (auth.isAuthenticated) {
      try {
        await useClusterStore().load()
      } catch {
        // 클러스터 로드 실패가 앱 기동을 막아선 안 된다.
      }
    }
  }

  app.use(router)
  await router.isReady()
  app.mount('#app')
}

void bootstrap()
