<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { opsApi, type Notice } from '@/api/ops'
import Chip from '@/components/ui/Chip.vue'

/**
 * 톱바 공지 메뉴 (U-CL-03).
 *
 * 공지는 **포털 전체 대상**이라 클러스터 선택과 무관하다. 그래서 사이드바(클러스터 종속
 * 화면들)가 아니라 톱바에 둔다 — 어느 화면에서도 같은 것이 보여야 한다.
 */
const props = defineProps<{ open: boolean }>()
defineEmits<{ toggle: []; close: [] }>()

const notices = ref<Notice[]>([])
const failed = ref(false)

onMounted(async () => {
  try {
    notices.value = await opsApi.notices()
  } catch {
    // 공지를 못 읽었다고 톱바가 깨지면 안 된다 — 조용히 비우고 표시만 남긴다.
    failed.value = true
  }
})

/**
 * 노출 기간으로 상태를 나눈다. **지난 공지와 진행 중인 공지가 같아 보이면 안 된다** —
 * 끝난 점검 안내를 보고 작업을 미루는 일이 생긴다. 기간이 비어 있으면 상시 공지다.
 */
type Phase = 'active' | 'scheduled' | 'ended'

function phaseOf(n: Notice): Phase {
  const now = Date.now()
  if (n.start_at && new Date(n.start_at).getTime() > now) return 'scheduled'
  if (n.end_at && new Date(n.end_at).getTime() < now) return 'ended'
  return 'active'
}

const PHASE_LABEL: Record<Phase, string> = { active: '진행 중', scheduled: '예정', ended: '종료' }
const PHASE_TONE: Record<Phase, 'brand' | 'violet' | 'gray'> = {
  active: 'brand',
  scheduled: 'violet',
  ended: 'gray',
}

/** 진행 중 → 예정 → 종료 순. 같은 상태 안에서는 서버 순서(최신 우선)를 유지한다. */
const ORDER: Record<Phase, number> = { active: 0, scheduled: 1, ended: 2 }
const sorted = computed(() =>
  [...notices.value]
    .map((n, i) => ({ notice: n, phase: phaseOf(n), i }))
    .sort((a, b) => ORDER[a.phase] - ORDER[b.phase] || a.i - b.i),
)

/** 배지는 **진행 중인 것만** 센다 — 끝난 공지까지 세면 숫자가 줄지 않아 무시하게 된다. */
const activeCount = computed(() => sorted.value.filter((r) => r.phase === 'active').length)

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString('ko-KR') : ''
}

function period(n: Notice): string {
  if (!n.start_at && !n.end_at) return '상시'
  return `${when(n.start_at) || '—'} ~ ${when(n.end_at) || '—'}`
}
</script>

<template>
  <div class="relative">
    <button
      class="relative flex items-center px-2.5 py-1.5 rounded-lg border border-line text-[14px] hover:bg-bg"
      :aria-label="`공지 ${activeCount}건`"
      @click="$emit('toggle')"
    >
      <span class="text-[16px]" aria-hidden="true">📢</span>
      <span
        v-if="activeCount"
        class="absolute -top-1 -right-1 min-w-[17px] h-[17px] px-1 rounded-full bg-err
               text-white text-[11px] font-bold grid place-items-center"
      >{{ activeCount }}</span>
    </button>

    <div
      v-if="props.open"
      class="absolute right-0 mt-1.5 w-[360px] max-h-[70vh] overflow-y-auto bg-surface
             border border-line rounded-card shadow-pop"
    >
      <p class="px-3.5 py-2.5 text-[12px] font-bold text-ink-3 uppercase border-b border-line">
        공지사항
      </p>

      <p v-if="failed" class="px-3.5 py-3 text-[14px] text-ink-3">공지를 불러오지 못했습니다.</p>
      <p v-else-if="!sorted.length" class="px-3.5 py-3 text-[14px] text-ink-3">
        등록된 공지가 없습니다.
      </p>

      <!-- 끝난 공지는 흐리게 — 목록에서 지우면 "왜 없어졌지"가 되고, 같게 두면 오해한다 -->
      <div
        v-for="row in sorted"
        :key="row.notice.id"
        class="px-3.5 py-3 border-b border-line last:border-0"
        :class="row.phase === 'ended' ? 'opacity-55' : ''"
      >
        <div class="flex items-start gap-2">
          <b class="flex-1 text-[14.5px] text-ink">{{ row.notice.title }}</b>
          <Chip :tone="PHASE_TONE[row.phase]">{{ PHASE_LABEL[row.phase] }}</Chip>
        </div>
        <p
          v-if="row.notice.body"
          class="mt-1 text-[13.5px] text-ink-2 whitespace-pre-wrap"
        >{{ row.notice.body }}</p>
        <p class="mt-1.5 text-[12px] text-ink-3 mono">{{ period(row.notice) }}</p>
      </div>
    </div>
  </div>
</template>
