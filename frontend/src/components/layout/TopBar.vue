<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useClusterStore } from '@/stores/cluster'
import { CONSOLE_HOME, CONSOLE_LABEL, useConsole, type Console } from '@/router/console'
import NoticeMenu from './NoticeMenu.vue'

const auth = useAuthStore()
const clusters = useClusterStore()
const router = useRouter()

const openMenu = ref<'notice' | 'cluster' | 'account' | null>(null)
function toggle(menu: 'notice' | 'cluster' | 'account') {
  openMenu.value = openMenu.value === menu ? null : menu
}

const initials = computed(() => (auth.me?.username ?? '?').slice(0, 1).toUpperCase())

const currentConsole = useConsole()

/**
 * 전환 가능한 콘솔. 관리자가 아니면 사용자 포털뿐이다 — 눌러도 가드가 막는 항목을
 * 보여주지 않는다.
 */
const CONSOLE_ICON: Record<Console, string> = { portal: '⚙', cluster: '◈', user: '↪' }

/**
 * 클러스터 선택기와 `Global` 표시가 **같은 폭**이어야 콘솔을 오갈 때 톱바가 안 흔들린다.
 * 두 곳에 따로 적으면 한쪽만 고쳐져 어긋나므로 한 상수에서 쓴다.
 * 긴 클러스터명은 잘린다 — 전체 이름은 드롭다운과 툴팁에 있다.
 */
const SELECTOR_CLASS =
  'w-[190px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-line text-[14px]'
const consoles = computed<Console[]>(() =>
  auth.isAdmin ? ['portal', 'cluster', 'user'] : ['user'],
)

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
    <RouterLink :to="CONSOLE_HOME[currentConsole]" class="font-bold text-brand-700">
      Digital Twin Platform
    </RouterLink>

    <div class="ml-auto flex items-center gap-1.5">
      <!-- 공지는 클러스터에 종속되지 않아 사이드바가 아니라 여기 있다 -->
      <NoticeMenu :open="openMenu === 'notice'" @toggle="toggle('notice')" />

      <!--
        포탈 설정 화면들은 선택 클러스터를 보지 않는다. 그렇다고 선택기를 **없애면**
        옆 버튼들이 통째로 밀려 콘솔을 오갈 때마다 톱바가 튄다. 자리는 지키되
        비활성 `Global`로 바꿔 "고를 것이 없다"를 그 자리에서 말하게 한다.
      -->
      <div class="relative">
        <span
          v-if="currentConsole === 'portal'"
          :class="[SELECTOR_CLASS, 'bg-bg text-ink-3 cursor-default select-none']"
          title="포탈 설정은 클러스터와 무관합니다"
        >
          <span class="text-[16px]" aria-hidden="true">🌐</span>
          <span class="flex-1 font-semibold truncate text-left">Global</span>
        </span>
        <button
          v-else
          :class="[SELECTOR_CLASS, 'hover:bg-bg']"
          :title="clusters.selectedName"
          @click="toggle('cluster')"
        >
          <span class="text-[16px]" aria-hidden="true">🖧</span>
          <span class="flex-1 font-semibold truncate text-left">{{ clusters.selectedName }}</span>
          <span class="text-ink-3 text-[11px] shrink-0">▾</span>
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
            <span class="flex-1 truncate">{{ c.alias || c.name || '이름 미확인' }}</span>
            <code class="text-[12px] text-ink-3 mono">{{ c.name ?? '—' }}</code>
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
            v-for="c in consoles"
            :key="c"
            :to="CONSOLE_HOME[c]"
            class="flex items-center gap-2 px-3 py-2 text-[14px] hover:bg-bg"
            :class="c === currentConsole ? 'text-brand-700 font-semibold' : 'text-ink-2'"
            @click="openMenu = null"
          >
            <span class="w-4 text-center" aria-hidden="true">{{ CONSOLE_ICON[c] }}</span>
            <span class="flex-1">{{ CONSOLE_LABEL[c] }}</span>
            <span v-if="c === currentConsole" class="text-[12px]">현재</span>
          </RouterLink>
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
