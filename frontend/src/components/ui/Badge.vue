<script setup lang="ts">
import { computed } from 'vue'

/** Slurm/노드 상태 → 색. 알 수 없는 상태는 회색으로 떨어뜨린다. */
const props = withDefaults(defineProps<{ state?: string; plain?: boolean }>(), { state: 'idle' })

const TONE: Record<string, string> = {
  running: 'bg-info-bg text-info', alloc: 'bg-info-bg text-info',
  pending: 'bg-warn-bg text-warn', drain: 'bg-warn-bg text-warn',
  completed: 'bg-ok-bg text-ok', idle: 'bg-ok-bg text-ok', ok: 'bg-ok-bg text-ok',
  failed: 'bg-err-bg text-err', down: 'bg-err-bg text-err',
  cancelled: 'bg-idle-bg text-idle', mix: 'bg-violet-bg text-violet',
}
const tone = computed(() => TONE[props.state.toLowerCase()] ?? 'bg-idle-bg text-idle')
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap"
    :class="tone"
  >
    <i v-if="!plain" class="w-1.5 h-1.5 rounded-full bg-current" />
    <slot />
  </span>
</template>
