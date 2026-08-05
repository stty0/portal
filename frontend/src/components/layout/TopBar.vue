<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useClusterStore } from '@/stores/cluster'

const auth = useAuthStore()
const clusters = useClusterStore()
const router = useRouter()

const openMenu = ref<'cluster' | 'account' | null>(null)
function toggle(menu: 'cluster' | 'account') {
  openMenu.value = openMenu.value === menu ? null : menu
}

const initials = computed(() => (auth.me?.username ?? '?').slice(0, 1).toUpperCase())

async function logout() {
  await auth.logout()
  clusters.reset()
  router.push({ name: 'login' })
}

function pickCluster(id: number) {
  clusters.select(id)
  openMenu.value = null
  // 목록/상세는 선택 클러스터에 종속되므로 현재 화면을 다시 읽게 한다.
  router.go(0)
}
</script>

<template>
  <header
    class="h-14 shrink-0 bg-surface border-b border-line flex items-center gap-3 px-4 relative z-30"
  >
    <RouterLink :to="auth.isAdmin ? '/admin/dashboard' : '/cluster'" class="font-bold text-brand-700">
      Digital Twin Platform
    </RouterLink>

    <!--
      검색창은 바 전체 기준으로 가운데. 좌측 브랜드·우측 메뉴의 폭이 서로 달라
      flex 흐름에 두면 절대 가운데에 오지 않으므로 흐름에서 빼서 절대 배치한다.
      폭을 30vw로 묶은 건 좁은 화면에서 양옆 요소와 겹치지 않게 하기 위해서다.
    -->
    <div
      class="hidden md:flex absolute left-1/2 -translate-x-1/2 w-[min(28rem,30vw)] items-center gap-2 px-3 py-1.5 rounded-lg bg-bg text-ink-3"
    >
      <span class="text-[16px]" aria-hidden="true">🔍</span>
      <input
        class="flex-1 bg-transparent text-[14px] outline-none placeholder:text-ink-3"
        placeholder="사용자, Job ID, 노드 검색"
      />
    </div>

    <div class="ml-auto flex items-center gap-1.5">
      <!-- 전역 클러스터 스코프 — 운영 화면은 여기서 고른 클러스터 기준으로 표시된다 -->
      <div class="relative">
        <button
          class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-line text-[14px] hover:bg-bg"
          @click="toggle('cluster')"
        >
          <span class="text-[16px]" aria-hidden="true">🖧</span>
          <span class="font-semibold">{{ clusters.selectedName }}</span>
          <span class="text-ink-3 text-[11px]">▾</span>
        </button>
        <div
          v-if="openMenu === 'cluster'"
          class="absolute right-0 mt-1.5 w-64 bg-surface border border-line rounded-card shadow-pop py-1.5"
        >
          <p class="px-3 py-1.5 text-[12px] font-bold text-ink-3 uppercase">클러스터 선택</p>
          <button
            v-for="c in clusters.clusters"
            :key="c.id"
            class="w-full flex items-center gap-2 px-3 py-2 text-[14px] hover:bg-bg text-left"
            :class="c.id === clusters.selectedId ? 'text-brand-700 font-semibold' : 'text-ink-2'"
            @click="pickCluster(c.id)"
          >
            <span class="flex-1 truncate">{{ c.description || c.name }}</span>
            <code class="text-[12px] text-ink-3 mono">{{ c.name }}</code>
          </button>
          <p v-if="!clusters.clusters.length" class="px-3 py-2 text-[14px] text-ink-3">
            등록된 클러스터가 없습니다.
          </p>
        </div>
      </div>

      <span class="w-px h-5 bg-line mx-1" aria-hidden="true" />

      <div class="relative">
        <button
          class="w-8 h-8 rounded-full bg-brand-700 text-white text-[12px] font-bold grid place-items-center"
          @click="toggle('account')"
        >{{ initials }}</button>
        <div
          v-if="openMenu === 'account'"
          class="absolute right-0 mt-1.5 w-60 bg-surface border border-line rounded-card shadow-pop py-1.5"
        >
          <div class="px-3 py-2 border-b border-line">
            <b class="block text-[14.5px]">{{ auth.me?.display_name || auth.me?.username }}</b>
            <small class="text-[12.5px] text-ink-3">{{ auth.me?.username }} · {{ auth.me?.role }}</small>
          </div>
          <RouterLink
            v-if="auth.isAdmin"
            to="/admin/dashboard"
            class="block px-3 py-2 text-[14px] text-ink-2 hover:bg-bg"
            @click="openMenu = null"
          >⚙ 관리자 콘솔로</RouterLink>
          <RouterLink
            to="/cluster"
            class="block px-3 py-2 text-[14px] text-ink-2 hover:bg-bg"
            @click="openMenu = null"
          >↪ 사용자 포털로</RouterLink>
          <button
            class="w-full text-left px-3 py-2 text-[14px] text-err hover:bg-bg"
            @click="logout"
          >⏻ 로그아웃</button>
        </div>
      </div>
    </div>
  </header>

  <!-- 드롭다운 바깥 클릭으로 닫기 -->
  <div v-if="openMenu" class="fixed inset-0 z-20" @click="openMenu = null" />
</template>
