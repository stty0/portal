<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'gray' | 'brand' | 'cluster' | 'violet' }>(), { tone: 'gray' })
const TONE = {
  gray: 'bg-idle-bg text-ink-2',
  brand: 'bg-brand-100 text-brand-700',
  cluster: 'bg-info-bg text-info',
  violet: 'bg-violet-bg text-violet',
} as const
</script>

<template>
  <span class="inline-block px-2 py-0.5 rounded-md text-[12.5px] font-semibold" :class="TONE[tone]">
    <slot />
  </span>
</template>
