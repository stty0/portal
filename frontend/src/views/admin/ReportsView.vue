<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  reportApi,
  type UsageReport,
  type UsageRow,
  type UtilizationReport,
  type WaitTimeReport,
} from '@/api/reports'
import { useClusterStore } from '@/stores/cluster'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-14 — 세 리포트 모두 slurmdbd의 완료 Job에서 파생된다 (A-RP-01·02·03). */
const clusters = useClusterStore()
const days = ref(30)
const loading = ref(false)
const usage = ref<UsageReport | null>(null)
const util = ref<UtilizationReport | null>(null)
const wait = ref<WaitTimeReport | null>(null)
const errors = ref<{ usage: unknown; util: unknown; wait: unknown }>({
  usage: null,
  util: null,
  wait: null,
})
const group = ref<'by_user' | 'by_account' | 'by_partition'>('by_user')

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  // 셋은 서로 독립이다 — 하나가 실패해도 나머지는 보여준다.
  const [u, t, w] = await Promise.allSettled([
    reportApi.usage(cid, days.value),
    reportApi.utilization(cid, days.value),
    reportApi.waitTime(cid, days.value),
  ])
  usage.value = u.status === 'fulfilled' ? u.value : null
  util.value = t.status === 'fulfilled' ? t.value : null
  wait.value = w.status === 'fulfilled' ? w.value : null
  errors.value = {
    usage: u.status === 'rejected' ? u.reason : null,
    util: t.status === 'rejected' ? t.reason : null,
    wait: w.status === 'rejected' ? w.reason : null,
  }
  loading.value = false
}
watch([() => clusters.selectedId, days], load, { immediate: true })

const rows = computed<UsageRow[]>(() => usage.value?.[group.value] ?? [])
const peakUsage = computed(() => Math.max(1, ...rows.value.map((r) => r.cpu_hours)))
const peakDaily = computed(() => Math.max(1, ...(util.value?.daily ?? []).map((d) => d.cpu_hours)))
const peakBucket = computed(() =>
  Math.max(1, ...(wait.value?.histogram ?? []).map((h) => h.count)),
)

/** 대기시간은 초로 오지만 사람이 읽는 단위로 바꾼다. */
function duration(seconds: number | null): string {
  if (seconds === null) return '—'
  if (seconds < 60) return `${Math.round(seconds)}초`
  if (seconds < 3600) return `${Math.round(seconds / 60)}분`
  return `${(seconds / 3600).toFixed(1)}시간`
}

const inputClass =
  'px-3 py-2 border border-line rounded-lg text-[14.5px] outline-none focus:border-brand-500'
</script>

<template>
  <PageHead
    title="통계 / 리포트"
    :crumbs="['HPC Portal Admin', '운영']"
    :sub="`기간별 사용량·가동률·대기시간 · ${clusters.selectedName}`"
  >
    <template #actions>
      <select v-model.number="days" :class="inputClass">
        <option :value="7">최근 7일</option>
        <option :value="30">최근 30일</option>
        <option :value="90">최근 90일</option>
      </select>
      <Btn @click="load">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="사용량 리포트" flush>
      <template #title-extra><Fid id="A-RP-01" /></template>
      <template #head>
        <Chip v-if="usage" tone="gray">
          {{ usage.total_jobs }} Job · {{ usage.total_cpu_hours }} CPU-시간
        </Chip>
      </template>
      <ErrorNote :error="errors.usage" class="m-4" />
      <div v-if="usage" class="px-4 py-3 border-b border-line flex flex-wrap gap-2 items-center">
        <div class="flex rounded-lg border border-line overflow-hidden text-[14px]">
          <button
            v-for="g in (['by_user', 'by_account', 'by_partition'] as const)"
            :key="g"
            class="px-3 py-1.5"
            :class="group === g ? 'bg-brand-700 text-white font-semibold' : 'bg-surface text-ink-2'"
            @click="group = g"
          >{{ g === 'by_user' ? '사용자별' : g === 'by_account' ? '계정별' : '파티션별' }}</button>
        </div>
        <span class="text-[13px] text-ink-3">{{ usage.start }} ~ {{ usage.end }}</span>
      </div>
      <Empty v-if="usage && !rows.length" text="기간 내 완료된 Job이 없습니다." />
      <Table
        v-else-if="usage"
        :columns="[
          { key: 'key', label: group === 'by_user' ? '사용자' : group === 'by_account' ? '계정' : '파티션' },
          { key: 'bar', label: 'CPU-시간 비중' },
          { key: 'hours', label: 'CPU-시간', num: true },
          { key: 'jobs', label: 'Job', num: true },
          { key: 'failed', label: '실패', num: true },
        ]"
      >
        <tr v-for="r in rows" :key="r.key" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ r.key }}</td>
          <td class="px-3.5 py-2.5">
            <div class="h-2.5 rounded bg-idle-bg overflow-hidden">
              <div class="h-full rounded bg-brand-700" :style="{ width: (r.cpu_hours / peakUsage) * 100 + '%' }" />
            </div>
          </td>
          <td class="px-3.5 py-2.5 mono text-right">{{ r.cpu_hours }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ r.jobs }}</td>
          <td class="px-3.5 py-2.5 mono text-right" :class="r.failed ? 'text-err' : 'text-ink-3'">
            {{ r.failed }}
          </td>
        </tr>
      </Table>
    </Card>

    <Card title="가동률 추이" flush>
      <template #title-extra><Fid id="A-RP-02" /></template>
      <template #head>
        <Chip v-if="util" tone="gray">
          {{ util.total_cpus }} CPU · 하루 용량 {{ util.daily_capacity_cpu_hours }} CPU-시간
        </Chip>
      </template>
      <ErrorNote :error="errors.util" class="m-4" />
      <Empty v-if="!util" text="가동률 데이터가 없습니다." />
      <div v-else class="p-4 space-y-1.5">
        <div v-for="d in util.daily" :key="d.date" class="flex items-center gap-3">
          <span class="w-24 shrink-0 mono text-[13px] text-ink-3">{{ d.date }}</span>
          <div class="flex-1 h-3 rounded bg-idle-bg overflow-hidden">
            <div class="h-full rounded bg-brand-700" :style="{ width: (d.cpu_hours / peakDaily) * 100 + '%' }" />
          </div>
          <span class="w-24 shrink-0 mono text-[13px] text-right">{{ d.cpu_hours }}h</span>
          <span class="w-16 shrink-0 mono text-[13px] text-right text-ink-3">
            {{ d.pct === null ? '—' : d.pct + '%' }}
          </span>
        </div>
      </div>
      <template #foot>
        가동률 = 사용 CPU-시간 ÷ (현재 노드 CPU 합 × 24h). 기간 중 노드 구성이 바뀌었다면
        과거 구간은 근사치입니다.
      </template>
    </Card>

    <Card title="대기시간 분석" flush>
      <template #title-extra><Fid id="A-RP-03" /></template>
      <ErrorNote :error="errors.wait" class="m-4" />
      <Empty v-if="!wait || !wait.samples" text="대기시간을 계산할 Job이 없습니다." />
      <template v-else>
        <div class="px-4 py-3 border-b border-line flex flex-wrap gap-5 items-center">
          <span class="text-[13px] text-ink-3">표본 <b class="mono text-ink">{{ wait.samples }}</b></span>
          <span class="text-[13px] text-ink-3">평균 <b class="mono text-ink">{{ duration(wait.avg_seconds) }}</b></span>
          <span class="text-[13px] text-ink-3">중앙값 <b class="mono text-ink">{{ duration(wait.median_seconds) }}</b></span>
          <span class="text-[13px] text-ink-3">최대 <b class="mono text-ink">{{ duration(wait.max_seconds) }}</b></span>
        </div>
        <div class="p-4 space-y-1.5">
          <div v-for="h in wait.histogram" :key="h.label" class="flex items-center gap-3">
            <span class="w-24 shrink-0 text-[13px] text-ink-3">{{ h.label }}</span>
            <div class="flex-1 h-3 rounded bg-idle-bg overflow-hidden">
              <div class="h-full rounded bg-brand-700" :style="{ width: (h.count / peakBucket) * 100 + '%' }" />
            </div>
            <span class="w-16 shrink-0 mono text-[13px] text-right">{{ h.count }}</span>
          </div>
        </div>
        <Table
          v-if="wait.by_partition.length"
          :columns="[
            { key: 'p', label: '파티션' },
            { key: 'n', label: '표본', num: true },
            { key: 'avg', label: '평균 대기', num: true },
            { key: 'max', label: '최대 대기', num: true },
          ]"
        >
          <tr v-for="p in wait.by_partition" :key="p.partition" class="border-b border-line last:border-0">
            <td class="px-3.5 py-2.5 mono font-semibold">{{ p.partition }}</td>
            <td class="px-3.5 py-2.5 mono text-right">{{ p.samples }}</td>
            <td class="px-3.5 py-2.5 mono text-right">{{ duration(p.avg_seconds) }}</td>
            <td class="px-3.5 py-2.5 mono text-right">{{ duration(p.max_seconds) }}</td>
          </tr>
        </Table>
      </template>
      <template #foot>
        제출 → 시작까지의 지연입니다. 시작되지 못한 Job(취소 등)은 표본에서 제외합니다.
      </template>
    </Card>
  </div>
</template>
