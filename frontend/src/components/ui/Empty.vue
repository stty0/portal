<script setup lang="ts">
defineProps<{ text?: string }>()
</script>
<template>
  <div class="py-12 text-center text-ink-3 text-[13.5px]">{{ text ?? '표시할 항목이 없습니다.' }}</div>
</template>
