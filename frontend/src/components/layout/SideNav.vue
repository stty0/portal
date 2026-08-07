<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { router } from '@/router'
import type { Console } from '@/router/console'

/**
 * 사이드바 — 정적 프로토타입에서는 22개 파일에 복붙돼 있었다(CLAUDE.md 구조 규칙).
 * 여기 하나로 모았으므로 메뉴 변경은 이 파일만 고치면 된다.
 * 메뉴 구성은 라우터 meta(console·group·icon·title)에서 파생한다 — 두 곳에 적지 않는다.
 * `meta.console`이 어느 사이드바인지를, `meta.group`이 그 안의 소제목을 정한다.
 */
const props = defineProps<{ console: Console }>()
const route = useRoute()

const COLLAPSE_KEY = 'hpc-snb-collapsed'
const collapsed = ref(localStorage.getItem(COLLAPSE_KEY) === '1')
watch(collapsed, (v) => localStorage.setItem(COLLAPSE_KEY, v ? '1' : ''))

interface NavItem {
  name: string
  path: string
  title: string
  icon: string
  staticOnly: boolean
}

const groups = computed(() => {
  const result = new Map<string, NavItem[]>()
  for (const r of router.getRoutes()) {
    if (!r.meta.group || !r.name) continue
    // 사용자 포털 화면은 meta.console이 없다 — 'user'로 정규화해 비교한다.
    if ((r.meta.console ?? 'user') !== props.console) continue
    const list = result.get(r.meta.group) ?? []
    list.push({
      name: String(r.name),
      path: r.path,
      title: r.meta.title ?? String(r.name),
      icon: r.meta.icon ?? '·',
      staticOnly: Boolean(r.meta.staticOnly),
    })
    result.set(r.meta.group, list)
  }
  return result
})

/**
 * 활성 메뉴는 **현재 경로에 들어맞는 것 중 가장 구체적인 하나**다.
 *
 * 접두어만 보면 `/jobs/submit`에서 `Job 목록`(/jobs)과 `Job 제출`이 함께 켜진다.
 * 그렇다고 정확히 일치만 보면 `/jobs/123`(상세)에서 아무것도 안 켜진다.
 * 그래서 후보를 모은 뒤 경로가 가장 긴 것만 남긴다.
 */
const activePath = computed(() => {
  const matches = [...groups.value.values()]
    .flat()
    .filter((i) => route.path === i.path || route.path.startsWith(i.path.replace(/\/$/, '') + '/'))
    .sort((a, b) => b.path.length - a.path.length)
  return matches[0]?.path
})

function isActive(item: NavItem): boolean {
  return item.path === activePath.value
}

const SUBTITLE: Record<Console, string> = {
  portal: 'Portal Settings',
  cluster: 'Cluster Admin',
  user: 'User Portal',
}
</script>

<template>
  <aside
    class="bg-side-bg text-side-ink flex flex-col shrink-0 transition-[width] duration-150"
    :class="collapsed ? 'w-[64px]' : 'w-[248px]'"
  >
    <div
      class="flex items-center gap-2.5 h-14 border-b border-white/10"
      :class="collapsed ? 'justify-center px-0' : 'px-4'"
    >
      <span
        v-if="!collapsed"
        class="w-7 h-7 shrink-0 rounded-lg bg-brand-600 text-white grid place-items-center font-bold text-[15px]"
      >H</span>
      <span v-if="!collapsed" class="flex-1 min-w-0 leading-tight">
        <b class="block text-side-act text-[14.5px]">HPC Portal</b>
        <small class="block text-[12px] text-side-ink/70">{{ SUBTITLE[props.console] }}</small>
      </span>
      <button
        class="text-side-ink hover:text-side-act text-[15px]"
        :title="collapsed ? '펼치기' : '접기'"
        @click="collapsed = !collapsed"
      >{{ collapsed ? '☰' : '⇤' }}</button>
    </div>

    <nav class="flex-1 overflow-y-auto py-3">
      <template v-for="[group, items] in groups" :key="group">
        <p
          v-if="!collapsed"
          class="px-4 pt-3 pb-1.5 text-[11.5px] font-bold uppercase tracking-wider text-side-ink/50"
        >{{ group }}</p>
        <RouterLink
          v-for="item in items"
          :key="item.name"
          :to="item.path"
          :title="item.title"
          class="flex items-center gap-2.5 mx-2 px-2.5 py-2 rounded-lg text-[14.5px] transition-colors"
          :class="
            isActive(item)
              ? 'bg-white/12 text-side-act font-semibold'
              : 'hover:bg-white/6 hover:text-side-act'
          "
        >
          <span class="w-5 text-center shrink-0 text-[17px]" aria-hidden="true">{{ item.icon }}</span>
          <span v-if="!collapsed" class="flex-1 truncate">{{ item.title }}</span>
          <!-- 아직 API가 없는 화면임을 메뉴에서부터 알린다 -->
          <span
            v-if="!collapsed && item.staticOnly"
            class="text-[10.5px] px-1 py-px rounded bg-white/10 text-side-ink/70 shrink-0"
            title="정적 데이터 — 백엔드 미연결"
          >静</span>
        </RouterLink>
      </template>
    </nav>
  </aside>
</template>
