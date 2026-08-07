<script setup lang="ts">
defineProps<{ title?: string; sub?: string; flush?: boolean }>()
</script>

<template>
  <!-- flex 세로 배치 — 나란히 놓인 카드의 높이를 맞출 때 본문이 남는 공간을 먹고
       바닥글이 아래에 붙는다. 높이가 자유로우면 지금까지와 똑같이 보인다. -->
  <section class="bg-surface border border-line rounded-card shadow-card flex flex-col">
    <header
      v-if="title || $slots.head"
      class="flex items-center gap-3 px-[18px] py-3 border-b border-line"
    >
      <h2 v-if="title" class="text-[16px] font-semibold text-ink flex items-center gap-2">
        {{ title }}
        <slot name="title-extra" />
      </h2>
      <span v-if="sub" class="text-[13px] text-ink-3">{{ sub }}</span>
      <div class="ml-auto flex items-center gap-2"><slot name="head" /></div>
    </header>
    <div :class="['flex-1', flush ? '' : 'p-[18px]']"><slot /></div>
    <footer v-if="$slots.foot" class="px-[18px] py-3 border-t border-line text-[14.5px] text-ink-3">
      <slot name="foot" />
    </footer>
  </section>
</template>
