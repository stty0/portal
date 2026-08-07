<script setup lang="ts">
import { useConsole } from '@/router/console'
import SideNav from './SideNav.vue'
import TopBar from './TopBar.vue'

// 콘솔은 라우트에서 파생한다 — 북마크로 열어도 맞는 셸로 들어와야 한다.
const currentConsole = useConsole()
</script>

<template>
  <div class="h-screen flex flex-col">
    <TopBar />
    <div class="flex-1 flex min-h-0">
      <SideNav :console="currentConsole" />
      <div class="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <!--
          본문은 화면 폭을 따라 늘어나되, 좌우 여백도 함께 커진다(clamp: 24px~80px).
          상한 2200px은 초광폭 모니터에서 표 한 줄이 시선을 벗어날 만큼 길어지는 것만 막는다.
        -->
        <main class="flex-1 w-full mx-auto max-w-[2200px] py-6 px-[clamp(1.5rem,3.5vw,5rem)]">
          <slot />
        </main>
        <footer class="border-t border-line text-[12.5px] text-ink-3">
          <div
            class="flex flex-wrap gap-x-2 gap-y-1 w-full mx-auto max-w-[2200px] py-4 px-[clamp(1.5rem,3.5vw,5rem)]"
          >
            <span>개인정보처리방침</span><span>|</span><span>이용약관</span><span>|</span>
            <span>Copyright SAMSUNG SDS. All rights reserved.</span>
            <b class="ml-auto text-ink-2">SAMSUNG SDS</b>
          </div>
        </footer>
      </div>
    </div>
  </div>
</template>
