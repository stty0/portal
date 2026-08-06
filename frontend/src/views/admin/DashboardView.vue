<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { clusterApi, type ClusterEvent, type ClusterMetrics } from '@/api/clusters'
import { fileApi, type StorageResponse } from '@/api/files'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import { jobState, stateTone } from '@/utils/job'
import { resourceTone, type SlurmRecord } from '@/utils/slurm'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import Meter from '@/components/ui/Meter.vue'
import PageHead from '@/components/ui/PageHead.vue'

/**
 * SCR-10 대시보드.
 * 모든 패널이 실 API에서 온다. 부하(A-DB-02)는 Prometheus 없이 slurmctld의 노드 상태에서
 * 집계하고, 이벤트(A-DB-04)는 포털 감사 로그를 쓴다.
 */
const clusters = useClusterStore()
const error = ref<unknown>(null)
const loading = ref(false)
const counts = ref({ total: 0, running: 0, pending: 0, failed: 0 })
const nodes = ref<SlurmRecord[]>([])
const metrics = ref<ClusterMetrics | null>(null)
const events = ref<ClusterEvent[]>([])
const storage = ref<StorageResponse | null>(null)

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  error.value = null
  // 패널은 서로 독립이다 — 하나가 실패해도 나머지는 그린다.
  const [jobs, node, metric, event, store] = await Promise.allSettled([
    jobApi.list(cid),
    clusterApi.nodes(cid),
    clusterApi.metrics(cid),
    clusterApi.events(cid, 15),
    fileApi.storage(cid),
  ])
  if (jobs.status === 'fulfilled') {
    const tally = { total: jobs.value.items.length, running: 0, pending: 0, failed: 0 }
    for (const job of jobs.value.items) {
      const tone = stateTone(jobState(job))
      if (tone === 'running') tally.running++
      else if (tone === 'pending') tally.pending++
      else if (tone === 'failed') tally.failed++
    }
    counts.value = tally
  } else {
    error.value = jobs.reason
  }
  nodes.value = node.status === 'fulfilled' ? node.value : []
  metrics.value = metric.status === 'fulfilled' ? metric.value : null
  events.value = event.status === 'fulfilled' ? event.value : []
  storage.value = store.status === 'fulfilled' ? store.value : null
  loading.value = false
}

const when = (iso: string) => new Date(iso).toLocaleString('ko-KR')
function size(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = bytes
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`
}
onMounted(load)
watch(() => clusters.selectedId, load)
</script>

<template>
  <PageHead
    title="대시보드"
    :crumbs="['HPC Portal Admin', '모니터링']"
    :sub="`${clusters.selectedName} · 클러스터 현황 요약`"
  >
    <template #actions>
      <Btn @click="load">↻ 새로고침</Btn>
      <RouterLink to="/admin/jobs"><Btn variant="primary">☰ 전체 Job</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <Card title="Job 현황" class="mb-5">
    <template #title-extra><Fid id="A-DB-03" /></template>
    <div v-if="loading" class="py-6 text-center text-ink-3 text-[14.5px]">불러오는 중…</div>
    <div v-else class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="s in [
          { k: '전체', v: counts.total, tone: 'text-ink' },
          { k: 'Running', v: counts.running, tone: 'text-info' },
          { k: 'Pending', v: counts.pending, tone: 'text-warn' },
          { k: 'Failed', v: counts.failed, tone: 'text-err' },
        ]"
        :key="s.k"
      >
        <p class="text-[13.5px] text-ink-3 mb-1">{{ s.k }}</p>
        <p class="text-[32px] font-bold mono" :class="s.tone">{{ s.v }}</p>
      </div>
    </div>
  </Card>

  <div class="grid lg:grid-cols-2 gap-5 items-start">
    <Card title="노드 상태 맵">
      <template #title-extra><Fid id="A-DB-01" /></template>
      <Empty v-if="!nodes.length" text="노드 정보를 불러오지 못했습니다." />
      <!-- 노드가 늘어도 한눈에 보이도록 타일로 깐다 -->
      <div v-else class="flex flex-wrap gap-2">
        <div
          v-for="n in nodes"
          :key="String(n.name)"
          class="px-3 py-2 rounded-lg border border-line min-w-[140px]"
        >
          <div class="flex items-center justify-between gap-2 mb-1">
            <b class="mono text-[14px]">{{ n.name }}</b>
            <Badge :state="resourceTone(String((n.state as string[])?.[0] ?? ''))">
              {{ (n.state as string[])?.[0] ?? '—' }}
            </Badge>
          </div>
          <p class="text-[13px] text-ink-3 mono">
            CPU {{ n.alloc_cpus ?? 0 }}/{{ n.cpus ?? 0 }}
          </p>
        </div>
      </div>
    </Card>

    <Card title="실시간 부하">
      <template #title-extra><Fid id="A-DB-02" /></template>
      <Empty v-if="!metrics" text="부하 정보를 불러오지 못했습니다." />
      <div v-else class="space-y-4">
        <Meter
          label="CPU 할당"
          :value="metrics.cpu_pct ?? 0"
          :caption="`${metrics.alloc_cpus} / ${metrics.cpus} core`"
        />
        <Meter
          label="메모리 할당"
          :value="metrics.memory_pct ?? 0"
          :caption="`${size(metrics.alloc_memory_mb * 1024 * 1024)} / ${size(metrics.memory_mb * 1024 * 1024)}`"
        />
        <div class="flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
          <span>노드 {{ metrics.nodes }}</span>
          <Chip v-for="s in metrics.states" :key="s.state" tone="gray">
            {{ s.state }} {{ s.count }}
          </Chip>
          <span v-if="metrics.load_per_cpu !== null" class="ml-auto mono">
            load/CPU {{ metrics.load_per_cpu }}
          </span>
        </div>
      </div>
      <template #foot>
        Prometheus 없이 slurmctld의 노드 상태에서 집계한 현재 값입니다 — 시계열은 없습니다.
      </template>
    </Card>

    <Card title="최근 이벤트" flush>
      <template #title-extra><Fid id="A-DB-04" /></template>
      <Empty v-if="!events.length" text="기록된 이벤트가 없습니다." />
      <ul v-else class="divide-y divide-line">
        <li v-for="(e, i) in events" :key="i" class="px-4 py-2.5 flex items-start gap-3">
          <span class="mono text-[12.5px] text-ink-3 shrink-0 w-36">{{ when(e.at) }}</span>
          <span class="mono text-[13px] font-semibold shrink-0">{{ e.action }}</span>
          <span class="text-[13px] text-ink-2 truncate">{{ e.target || '—' }}</span>
          <span v-if="e.detail" class="text-[12.5px] text-ink-3 truncate ml-auto">{{ e.detail }}</span>
        </li>
      </ul>
      <template #foot>포털을 통해 일어난 조작 기록입니다 (감사 로그, C-05).</template>
    </Card>

    <Card title="스토리지 현황" flush>
      <template #title-extra><Fid id="A-DB-05" /></template>
      <Empty v-if="!storage?.targets.length" text="스토리지 정보를 불러오지 못했습니다." />
      <ul v-else class="divide-y divide-line">
        <li v-for="t in storage.targets" :key="t.label" class="px-4 py-3">
          <div v-if="t.exists">
            <Meter
              :label="`${t.label} · ${t.mount}`"
              :value="t.used_pct ?? 0"
              :caption="`${size(t.used_bytes ?? 0)} / ${size((t.used_bytes ?? 0) + (t.avail_bytes ?? 0))}`"
            />
          </div>
          <div v-else class="flex justify-between text-[14px]">
            <span>{{ t.label }}</span><span class="text-ink-3">없음</span>
          </div>
        </li>
      </ul>
    </Card>
  </div>
</template>
