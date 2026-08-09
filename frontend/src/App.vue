<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useClusterStore } from '@/stores/cluster'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const clusters = useClusterStore()

// 껍데기(사이드바·톱바) 없이 보여야 하는 화면.
//   public — 로그인·최초 설정
//   bare   — 새 탭으로 여는 인터랙티브 앱 화면. 앱이 창을 통째로 쓴다(JupyterLab이
//            자기 탭을 꽉 채우는 것과 같아야 한다). **인증과는 무관하다** —
//            라우터 가드는 `public`만 보고, `bare`는 그리는 방식만 정한다.
const bare = computed(() => Boolean(route.meta.public || route.meta.bare))

onMounted(() => {
  // 어떤 API든 401이면 세션이 끝난 것이다. 화면 곳곳에서 개별 처리하지 않는다.
  setUnauthorizedHandler(() => {
    auth.clear()
    clusters.reset()
    if (!route.meta.public) router.push({ name: 'login' })
  })
})
</script>

<template>
  <RouterView v-if="bare" />
  <AppShell v-else>
    <RouterView />
  </AppShell>
</template>
