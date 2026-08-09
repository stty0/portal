<script setup lang="ts">
import { num, type SlurmRecord } from '@/utils/slurm'

/**
 * 자원 한 종류의 사용/가용/전체.
 *
 * **가용을 굵게** 한다 — 이 화면에서 사용자가 찾는 답은 "지금 자리가 있나"다.
 * 값을 못 읽으면(자원이 아예 없는 파티션 등) 조용히 `—`로 둔다.
 *
 * 사용 + 가용이 전체보다 작을 수 있다 — DOWN·DRAIN 노드의 몫은 어느 쪽에도 안 들어간다.
 */
const props = defineProps<{
  usage: SlurmRecord
  /** 숫자를 사람이 읽는 단위로. 없으면 그대로 쓴다(개수). */
  format?: (value: number) => string
}>()

const show = (key: string): string => {
  const value = num(props.usage[key])
  if (value === null) return '—'
  return props.format ? props.format(value) : String(value)
}
</script>

<template>
  <span class="text-ink-3">{{ show('allocated') }}</span>
  <span class="text-line-dark"> / </span>
  <span class="text-ok font-semibold">{{ show('available') }}</span>
  <span class="text-line-dark"> / </span>
  <span>{{ show('total') }}</span>
</template>
