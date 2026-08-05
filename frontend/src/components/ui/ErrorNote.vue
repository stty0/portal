<script setup lang="ts">
import { PortalApiError } from '@/api/client'
const props = defineProps<{ error: unknown }>()
/** 백엔드 오류 코드를 감추지 않는다 — 원인 추적에 그게 가장 빠르다. */
function text(e: unknown): string {
  if (e instanceof PortalApiError) return `[${e.code}] ${e.message}`
  return e instanceof Error ? e.message : String(e)
}
</script>

<template>
  <div v-if="props.error" class="px-3.5 py-2.5 rounded-lg bg-err-bg text-err text-[14px] mb-4">
    {{ text(props.error) }}
  </div>
</template>
