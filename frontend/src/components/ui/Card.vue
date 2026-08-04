<script setup lang="ts">
defineProps<{ title?: string; sub?: string; flush?: boolean }>()
</script>

<template>
  <section class="bg-surface border border-line rounded-card shadow-card">
    <header
      v-if="title || $slots.head"
      class="flex items-center gap-3 px-[18px] py-3 border-b border-line"
    >
      <h2 v-if="title" class="text-[15px] font-semibold text-ink flex items-center gap-2">
        {{ title }}
        <slot name="title-extra" />
      </h2>
      <span v-if="sub" class="text-xs text-ink-3">{{ sub }}</span>
      <div class="ml-auto flex items-center gap-2"><slot name="head" /></div>
    </header>
    <div :class="flush ? '' : 'p-[18px]'"><slot /></div>
    <footer v-if="$slots.foot" class="px-[18px] py-3 border-t border-line text-[13.5px] text-ink-3">
      <slot name="foot" />
    </footer>
  </section>
</template>
