<script setup lang="ts">
defineProps<{ title: string; sub?: string; crumbs?: string[] }>()
</script>

<template>
  <div class="mb-5">
    <p v-if="crumbs?.length" class="text-[13px] text-ink-3 mb-1.5">{{ crumbs.join(' › ') }}</p>
    <div class="flex flex-wrap items-end gap-3">
      <div class="flex-1 min-w-0">
        <h1 class="text-[24px] font-bold text-ink tracking-tight">{{ title }}</h1>
        <p v-if="sub" class="mt-1 text-[14px] text-ink-3">{{ sub }}</p>
      </div>
      <!-- 버튼이 눌려 글자가 줄바꿈되지 않도록 축소 대신 줄바꿈으로 흘린다 -->
      <div class="flex flex-wrap justify-end items-center gap-2"><slot name="actions" /></div>
    </div>
  </div>
</template>
