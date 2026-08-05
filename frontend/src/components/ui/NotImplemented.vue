<script setup lang="ts">
/**
 * 백엔드 미구현 영역.
 *
 * 가짜 데이터를 채워 두면 "동작하는 화면"으로 오인돼 검증과 의사결정이 틀어진다.
 * 실제 구현이므로 값을 지어내지 않고 비워 둔다.
 */
defineProps<{ api?: string; note?: string }>()
</script>

<template>
  <div class="py-14 px-6 text-center">
    <p class="text-[14.5px] text-ink-2 font-semibold">아직 제공되지 않는 기능입니다</p>
    <p class="mt-1.5 text-[13.5px] text-ink-3">
      {{ note ?? '백엔드 API가 구현되면 이 영역에 실제 데이터가 표시됩니다.' }}
    </p>
    <code v-if="api" class="mt-3 inline-block px-2 py-1 rounded bg-bg text-[12.5px] text-ink-3 mono">
      {{ api }}
    </code>
  </div>
</template>
