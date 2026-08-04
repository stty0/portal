<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { router } from '@/router'

/**
 * 사이드바 — 정적 프로토타입에서는 22개 파일에 복붙돼 있었다(CLAUDE.md 구조 규칙).
 * 여기 하나로 모았으므로 메뉴 변경은 이 파일만 고치면 된다.
 * 메뉴 구성은 라우터 meta(group·icon·title·admin)에서 파생한다 — 두 곳에 적지 않는다.
 */
const props = defineProps<{ admin: boolean }>()
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
    if (Boolean(r.meta.admin) !== props.admin) continue
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

function isActive(item: NavItem): boolean {
  return route.path === item.path || route.path.startsWith(item.path + '/')
}
</script>

<template>
  <aside
    class="bg-side-bg text-side-ink flex flex-col shrink-0 transition-[width] duration-150"
    :class="collapsed ? 'w-[60px]' : 'w-[232px]'"
  >
    <div class="flex items-center gap-2.5 h-14 px-4 border-b border-white/10">
      <span
        class="w-7 h-7 shrink-0 rounded-lg bg-brand-600 text-white grid place-items-center font-bold text-sm"
      >H</span>
      <span v-if="!collapsed" class="flex-1 min-w-0 leading-tight">
        <b class="block text-side-act text-[13.5px]">HPC Portal</b>
        <small class="block text-[11px] text-side-ink/70">{{ admin ? 'Admin Console' : 'User Portal' }}</small>
      </span>
      <button
        class="text-side-ink hover:text-side-act text-sm"
        :title="collapsed ? '펼치기' : '접기'"
        @click="collapsed = !collapsed"
      >{{ collapsed ? '☰' : '⇤' }}</button>
    </div>

    <nav class="flex-1 overflow-y-auto py-3">
      <template v-for="[group, items] in groups" :key="group">
        <p
          v-if="!collapsed"
          class="px-4 pt-3 pb-1.5 text-[10.5px] font-bold uppercase tracking-wider text-side-ink/50"
        >{{ group }}</p>
        <RouterLink
          v-for="item in items"
          :key="item.name"
          :to="item.path"
          :title="item.title"
          class="flex items-center gap-2.5 mx-2 px-2.5 py-2 rounded-lg text-[13.5px] transition-colors"
          :class="
            isActive(item)
              ? 'bg-white/12 text-side-act font-semibold'
              : 'hover:bg-white/6 hover:text-side-act'
          "
        >
          <span class="w-4 text-center shrink-0" aria-hidden="true">{{ item.icon }}</span>
          <span v-if="!collapsed" class="flex-1 truncate">{{ item.title }}</span>
          <!-- 아직 API가 없는 화면임을 메뉴에서부터 알린다 -->
          <span
            v-if="!collapsed && item.staticOnly"
            class="text-[9.5px] px-1 py-px rounded bg-white/10 text-side-ink/70 shrink-0"
            title="정적 데이터 — 백엔드 미연결"
          >静</span>
        </RouterLink>
      </template>
    </nav>
  </aside>
</template>
