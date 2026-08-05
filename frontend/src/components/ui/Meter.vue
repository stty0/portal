<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ label: string; value: number; max?: number; caption?: string }>()
const pct = computed(() => Math.min(100, Math.round((props.value / (props.max ?? 100)) * 100)))
// 사용률이 높을수록 경고색 — 한눈에 위험을 알아채야 한다.
const tone = computed(() => (pct.value >= 90 ? 'bg-err' : pct.value >= 75 ? 'bg-warn' : 'bg-brand-700'))
</script>

<template>
  <div>
    <div class="flex justify-between text-[14px] mb-1">
      <span class="text-ink-2">{{ label }}</span>
      <span class="text-ink-3 mono">{{ caption ?? `${pct}%` }}</span>
    </div>
    <div class="h-2 rounded-full bg-idle-bg overflow-hidden">
      <div class="h-full rounded-full transition-[width]" :class="tone" :style="{ width: pct + '%' }" />
    </div>
  </div>
</template>
