<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import SideNav from './SideNav.vue'
import TopBar from './TopBar.vue'

const route = useRoute()
// 관리자 콘솔 여부는 현재 경로로 정한다 — 사용자가 두 포털을 오갈 수 있어야 한다.
const isAdminArea = computed(() => route.path.startsWith('/admin'))
</script>

<template>
  <div class="h-screen flex flex-col">
    <TopBar />
    <div class="flex-1 flex min-h-0">
      <SideNav :admin="isAdminArea" />
      <div class="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <main class="flex-1 p-6 max-w-[1400px] w-full"><slot /></main>
        <footer class="px-6 py-4 border-t border-line text-[11.5px] text-ink-3">
          <div class="flex flex-wrap gap-x-2 gap-y-1">
            <span>개인정보처리방침</span><span>|</span><span>이용약관</span><span>|</span>
            <span>Copyright SAMSUNG SDS. All rights reserved.</span>
            <b class="ml-auto text-ink-2">SAMSUNG SDS</b>
          </div>
        </footer>
      </div>
    </div>
  </div>
</template>
