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
/** 전체 CPU-시간 대비 비중. 합계가 0이면 나눌 수 없다. */
function usageShare(row: UsageRow): string {
  const total = usage.value?.total_cpu_hours ?? 0
  if (!total) return '0'
  const pct = (row.cpu_hours / total) * 100
  return pct >= 10 || pct === 0 ? String(Math.round(pct)) : pct.toFixed(1)
}

/** Job 하나가 평균 얼마나 무거웠나. 같은 CPU-시간이라도 잔챙이 다수와 큰 Job 몇 개는 다르다. */
function avgPerJob(row: UsageRow): string {
  return row.jobs ? (row.cpu_hours / row.jobs).toFixed(2) : '—'
}

function failRate(row: UsageRow): string {
  return row.jobs ? Math.round((row.failed / row.jobs) * 100).toString() : '0'
}
/**
 * 가동률 요약. 막대만 있으면 "대충 이 정도"까지만 읽히므로 숫자를 함께 둔다.
 * 산출 불가(`pct === null`)인 날은 평균에서 제외한다 — 0으로 세면 평균이 내려간다.
 */
const utilStats = computed(() => {
  const daily = util.value?.daily ?? []
  const pcts = daily.map((d) => d.pct).filter((p): p is number => p !== null)
  if (!daily.length) return null
  return {
    avg: pcts.length ? +(pcts.reduce((a, b) => a + b, 0) / pcts.length).toFixed(1) : null,
    max: pcts.length ? Math.max(...pcts) : null,
    hours: +daily.reduce((a, d) => a + d.cpu_hours, 0).toFixed(2),
  }
})

/** 눈금 간격 — 30일이면 5일마다. 라벨이 겹치면 아무것도 안 읽힌다. */
const tickEvery = computed(() => Math.max(1, Math.ceil((util.value?.daily.length ?? 1) / 6)))

/**
 * 막대 높이는 **0~100% 고정 척도**다. 최대값 기준으로 늘리면 34%가 꽉 찬 막대로 보여
 * "거의 다 쓰고 있다"로 잘못 읽힌다 — 가동률은 용량 대비 비율이라 기준이 절대적이다.
 * 0보다 크면 최소 2px는 남긴다(안 그리면 '0'과 구분되지 않는다).
 */
function barHeight(pct: number | null): string {
  if (pct === null || pct <= 0) return '0'
  return `max(${Math.min(pct, 100)}%, 2px)`
}

function barTitle(d: { date: string; cpu_hours: number; pct: number | null }): string {
  const rate = d.pct === null ? '산출 불가' : `${d.pct}%`
  return `${d.date} · ${d.cpu_hours} CPU-시간 · 가동률 ${rate}`
}
const peakBucket = computed(() =>
  Math.max(1, ...(wait.value?.histogram ?? []).map((h) => h.count)),
)

/** Y축 눈금. 개수라 **정수여야** 한다 — 0·중간·최대 셋이면 크기를 읽기에 충분하다. */
const waitTicks = computed(() => {
  const peak = peakBucket.value
  return [...new Set([peak, Math.round(peak / 2), 0])]
})

/** 구간이 전체에서 차지하는 비중. 개수만 있으면 "많은 편인가"를 판단할 수 없다. */
function share(count: number): string {
  const total = wait.value?.samples ?? 0
  if (!total) return '0'
  const pct = (count / total) * 100
  return pct >= 10 || pct === 0 ? String(Math.round(pct)) : pct.toFixed(1)
}

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
    <!-- 가동률과 대기시간은 같은 질문("자원이 어떻게 쓰이고 있나")의 두 면이라
         나란히 둔다. 좁은 화면에서는 세로로 쌓인다. -->
    <div class="grid lg:grid-cols-2 gap-5">
      <Card title="가동률 추이" flush>
        <template #title-extra><Fid id="A-RP-02" /></template>
        <template #head>
          <Chip v-if="util" tone="gray">
            {{ util.total_cpus }} CPU · 하루 용량 {{ util.daily_capacity_cpu_hours }} CPU-시간
          </Chip>
        </template>
        <ErrorNote :error="errors.util" class="m-4" />
        <Empty v-if="!util" text="가동률 데이터가 없습니다." />
        <template v-else>
          <div
            v-if="utilStats"
            class="px-4 py-3 border-b border-line flex flex-wrap items-center gap-5 text-[13px] text-ink-3"
          >
            <span>기간 <b class="mono text-ink">{{ util.start }} ~ {{ util.end }}</b></span>
            <span>평균 <b class="mono text-ink">{{ utilStats.avg === null ? '—' : utilStats.avg + '%' }}</b></span>
            <span>최대 <b class="mono text-ink">{{ utilStats.max === null ? '—' : utilStats.max + '%' }}</b></span>
            <span>합계 <b class="mono text-ink">{{ utilStats.hours }} CPU-시간</b></span>
          </div>
          <!-- X=날짜, Y=가동률. 척도는 0~100% 고정이다(barHeight 주석 참고). -->
          <div class="p-4 flex gap-2">
            <!-- Y축 눈금 -->
            <div class="w-9 shrink-0 relative h-52 mono text-[11px] text-ink-3">
              <span
                v-for="t in [100, 75, 50, 25, 0]" :key="t"
                class="absolute right-0 -translate-y-1/2" :style="{ top: 100 - t + '%' }"
              >{{ t }}%</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="relative h-52 border-l border-b border-line">
                <!-- 가로 격자 — 막대 뒤에 깔린다 -->
                <div
                  v-for="t in [25, 50, 75, 100]" :key="t"
                  class="absolute inset-x-0 border-t border-line" :style="{ top: 100 - t + '%' }"
                />
                <div class="absolute inset-0 flex items-end gap-px px-px">
                  <div
                    v-for="d in util.daily" :key="d.date"
                    class="flex-1 min-w-0 h-full flex items-end justify-center" :title="barTitle(d)"
                  >
                    <!-- 폭 상한 — 기간이 짧으면 막대가 컬럼 전체를 먹어 뭉툭해진다 -->
                    <div
                      class="w-full max-w-[26px] rounded-t bg-brand-700"
                      :style="{ height: barHeight(d.pct) }"
                    />
                  </div>
                </div>
              </div>
              <!-- X축 라벨 — 전부 쓰면 겹쳐서 아무것도 안 읽힌다 -->
              <div class="flex gap-px px-px mt-1.5">
                <!-- 칸이 좁아 `07-08`이 두 줄로 접힌다. 눈금 사이 칸은 비어 있으므로
                     한 줄로 두고 넘치게 둔다. -->
                <span
                  v-for="(d, i) in util.daily" :key="d.date"
                  class="flex-1 min-w-0 text-center mono text-[10px] text-ink-3 whitespace-nowrap"
                >{{ i % tickEvery === 0 ? d.date.slice(5) : '' }}</span>
              </div>
            </div>
          </div>
        </template>
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
          <!-- X=대기 구간, Y=Job 수. 옆의 가동률 차트와 형태를 맞춰 나란히 읽힌다.
               여기는 개수라 최대값 기준 척도가 맞다(가동률은 0~100% 고정). -->
          <div class="p-4 flex gap-2">
            <div class="w-9 shrink-0 relative h-52 mono text-[11px] text-ink-3">
              <span
                v-for="t in waitTicks" :key="t"
                class="absolute right-0 -translate-y-1/2"
                :style="{ top: 100 - (t / peakBucket) * 100 + '%' }"
              >{{ t }}</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="relative h-52 border-l border-b border-line">
                <div
                  v-for="t in waitTicks.filter((v) => v > 0)" :key="t"
                  class="absolute inset-x-0 border-t border-line"
                  :style="{ top: 100 - (t / peakBucket) * 100 + '%' }"
                />
                <div class="absolute inset-0 flex items-end gap-2 px-2">
                  <div
                    v-for="h in wait.histogram" :key="h.label"
                    class="flex-1 min-w-0 h-full flex items-end justify-center"
                    :title="`${h.label}: ${h.count}건 (${share(h.count)}%)`"
                  >
                    <div
                      class="w-full max-w-[40px] rounded-t bg-brand-700"
                      :style="{ height: h.count ? `max(${(h.count / peakBucket) * 100}%, 2px)` : '0' }"
                    />
                  </div>
                </div>
              </div>
              <!-- 개수만 있으면 "많은 편인가"를 판단할 수 없어 비중을 함께 적는다 -->
              <div class="flex gap-2 px-2 mt-1.5">
                <span
                  v-for="h in wait.histogram" :key="h.label"
                  class="flex-1 min-w-0 text-center text-[11px] text-ink-3 leading-tight"
                >
                  {{ h.label }}<br />
                  <b class="mono text-ink">{{ h.count }}</b>
                  <span class="mono"> · {{ share(h.count) }}%</span>
                </span>
              </div>
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
      <!-- 막대는 옆 칸 숫자를 그림으로 반복할 뿐이라 뺐다. 비중은 %로 바로 읽는다. -->
      <Table
        v-else-if="usage"
        :columns="[
          { key: 'key', label: group === 'by_user' ? '사용자' : group === 'by_account' ? '계정' : '파티션' },
          { key: 'hours', label: 'CPU-시간', num: true },
          { key: 'share', label: '비중', num: true },
          { key: 'node', label: '노드-시간', num: true },
          { key: 'jobs', label: 'Job', num: true },
          { key: 'avg', label: 'Job당 CPU-시간', num: true },
          { key: 'failed', label: '실패', num: true },
          { key: 'last', label: '최근 활동', num: true },
        ]"
      >
        <tr v-for="r in rows" :key="r.key" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ r.key }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ r.cpu_hours }}</td>
          <td class="px-3.5 py-2.5 mono text-right text-ink-3">{{ usageShare(r) }}%</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ r.node_hours }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ r.jobs }}</td>
          <!-- 잔챙이 Job이 많은지, 큰 Job 몇 개인지가 여기서 갈린다 -->
          <td class="px-3.5 py-2.5 mono text-right text-ink-3">{{ avgPerJob(r) }}</td>
          <!-- 개수만으로는 심각도를 모른다 — 37건 중 3건과 3건 중 3건은 다르다 -->
          <td class="px-3.5 py-2.5 mono text-right" :class="r.failed ? 'text-err' : 'text-ink-3'">
            {{ r.failed }}<span v-if="r.failed" class="text-[12px]"> · {{ failRate(r) }}%</span>
          </td>
          <td class="px-3.5 py-2.5 mono text-right text-ink-3">{{ r.last_active ?? '—' }}</td>
        </tr>
      </Table>
    </Card>
  </div>
</template>
