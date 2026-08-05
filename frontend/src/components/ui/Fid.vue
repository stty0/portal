<script setup lang="ts">
/** 기능 정의서 ID 칩 — 정적 프로토타입의 추적성을 그대로 유지한다(CLAUDE.md 구조 규칙). */
defineProps<{ id: string }>()
</script>

<template>
  <span
    class="inline-block px-1.5 py-px rounded border border-line-dark bg-bg text-[11.5px] font-semibold text-ink-3 align-middle mono"
    :title="`기능 정의서 ${id}`"
  >{{ id }}</span>
</template>
