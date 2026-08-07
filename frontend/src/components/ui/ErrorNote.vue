<script setup lang="ts">
import { computed } from 'vue'
import { PortalApiError } from '@/api/client'

const props = defineProps<{ error: unknown }>()

/** 백엔드 오류 코드를 감추지 않는다 — 원인 추적에 그게 가장 빠르다. */
const summary = computed(() => {
  const e = props.error
  if (e instanceof PortalApiError) return `[${e.code}] ${e.message}`
  return e instanceof Error ? e.message : String(e)
})

/**
 * `detail`까지 보여준다. 외부 서비스(slurmrestd·AD·SCP) 실패는 **본문에만 이유가 있다** —
 * 코드·메시지는 "호출이 실패했습니다"까지밖에 말해 주지 않아 그것만으로는 손쓸 수 없다.
 */
const detail = computed(() => {
  const e = props.error
  if (!(e instanceof PortalApiError) || e.detail == null) return ''
  const text = typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail)
  // 화면을 삼키지 않게 자른다. 전체는 서버 로그에 있다.
  return text.length > 600 ? text.slice(0, 600) + '…' : text
})
</script>

<template>
  <div v-if="props.error" class="px-3.5 py-2.5 rounded-lg bg-err-bg text-err text-[14px] mb-4">
    {{ summary }}
    <p v-if="detail" class="mt-1 text-[12.5px] mono opacity-80 break-all">{{ detail }}</p>
  </div>
</template>
