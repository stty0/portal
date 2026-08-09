<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import {
  canCancel, dependencyNoteText, dependencyText, formatDuration, formatTimestamp,
  formatTimestampFull, isBlockedForever, jobDependency, jobElapsedSeconds, jobEndedAt,
  jobField, jobId, jobStartedAt, jobState, parseDependency, stateTone, waitReasonText,
} from '@/utils/job'
import type { SlurmJob } from '@/types/api'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

const clusters = useClusterStore()
const jobs = ref<SlurmJob[]>([])
const loading = ref(false)
const error = ref<unknown>(null)
const state = ref('')
const partition = ref('')
const tab = ref<'active' | 'history'>('active')
/** 이력 출처. slurmdbd가 끊기면 slurmctld의 잔여 완료 Job으로 대체된다. */
const source = ref<string | null>(null)

/**
 * 컬럼은 탭마다 다르다.
 *   진행 중 — "얼마나 돌았나"가 관심사다. 의존성도 여기서만 의미가 있다.
 *   이력   — 시작·종료가 관심사다. **이력 응답의 dependency는 항상 null이다**(실측)
 *            — 빈 칸만 차지하므로 뺀다.
 */
const columns = computed(() =>
  tab.value === 'active'
    ? [
        { key: 'id', label: 'Job ID', width: '110px' },
        { key: 'name', label: '이름' },
        { key: 'state', label: '상태', width: '110px' },
        { key: 'elapsed', label: '수행 시간', width: '120px', num: true },
        { key: 'dependency', label: '의존성', width: '210px' },
        { key: 'partition', label: '파티션', width: '110px' },
        { key: 'account', label: '계정', width: '120px' },
        { key: 'nodes', label: '노드', width: '120px' },
        { key: 'actions', label: '액션', width: '150px' },
      ]
    : [
        { key: 'id', label: 'Job ID', width: '110px' },
        { key: 'name', label: '이름' },
        { key: 'state', label: '상태', width: '110px' },
        { key: 'start', label: '시작', width: '140px' },
        { key: 'end', label: '종료', width: '140px' },
        { key: 'elapsed', label: '수행 시간', width: '120px', num: true },
        { key: 'partition', label: '파티션', width: '110px' },
        { key: 'account', label: '계정', width: '120px' },
        { key: 'nodes', label: '노드', width: '120px' },
        { key: 'actions', label: '액션', width: '150px' },
      ],
)

/**
 * 흐르는 시계. 도는 Job의 수행 시간이 멈춰 보이면 값이 틀린 것처럼 읽힌다.
 *
 * **도는 Job이 있을 때만 돈다** — 이력만 보고 있을 때 1초마다 다시 그릴 이유가 없다
 * (인터랙티브 앱 목록의 폴링과 같은 태도).
 */
const now = ref(Math.floor(Date.now() / 1000))
let ticker: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  ticker = setInterval(() => {
    if (jobs.value.some((j) => jobState(j).toUpperCase().startsWith('RUN'))) {
      now.value = Math.floor(Date.now() / 1000)
    }
  }, 1000)
})
onBeforeUnmount(() => clearInterval(ticker))

/**
 * 앞 Job의 이름 — **지금 목록에 있을 때만.**
 *
 * 번호로 하나씩 조회하면 목록을 그리는 데 요청이 N개 붙는다. 끝난 Job은 Slurm이
 * 잊기도 해서(MinJobAge) 조회해도 없는 경우가 많다 — 이름은 있으면 좋은 정보이고,
 * 눌러서 가는 링크가 본체다.
 */
function nameOf(id: string): string {
  const found = jobs.value.find((j) => jobId(j) === id)
  return found ? jobField(found, 'name', '') : ''
}

async function load() {
  if (!clusters.selectedId) return
  loading.value = true
  error.value = null
  try {
    const filters = { state: state.value || undefined, partition: partition.value || undefined }
    const res =
      tab.value === 'active'
        ? await jobApi.list(clusters.selectedId, filters)
        : await jobApi.history(clusters.selectedId, { state: state.value || undefined })
    jobs.value = res.items
    source.value = tab.value === 'history' ? (res.source ?? null) : null
  } catch (e) {
    error.value = e
    jobs.value = []
    source.value = null
  } finally {
    loading.value = false
  }
}

watch([() => clusters.selectedId, tab], load, { immediate: true })

async function cancel(job: SlurmJob) {
  if (!clusters.selectedId) return
  if (!confirm(`Job ${jobId(job)} 을(를) 취소할까요?`)) return
  try {
    await jobApi.cancel(clusters.selectedId, jobId(job))
    await load()
  } catch (e) {
    error.value = e
  }
}

async function resubmit(job: SlurmJob) {
  if (!clusters.selectedId) return
  try {
    await jobApi.resubmit(clusters.selectedId, jobId(job))
    tab.value = 'active'
    await load()
  } catch (e) {
    error.value = e
  }
}

const filtered = computed(() => jobs.value)
</script>

<template>
  <PageHead
    title="Job 목록"
    :crumbs="['HPC Portal', 'Job']"
    :sub="`내 Job · ${clusters.selectedName} · 상태/파티션 필터`"
  >
    <template #actions>
      <Btn @click="load">↻ 새로고침</Btn>
      <RouterLink to="/jobs/submit"><Btn variant="primary">＋ Job 제출</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <!-- 이력이 slurmdbd가 아니라 slurmctld에서 온 경우, 목록이 불완전함을 밝힌다 -->
  <div
    v-if="source === 'slurmctld'"
    class="mb-3 px-3.5 py-2.5 rounded-lg bg-warn-bg text-warn text-[14px]"
  >
    slurmdbd에 연결할 수 없어 <b>최근 완료된 Job만</b> 표시합니다. 전체 이력을 보려면
    클러스터의 slurmdbd 연결을 확인하세요.
  </div>

  <Card flush>
    <template #head>
      <div class="flex flex-wrap items-center gap-2">
        <div class="flex rounded-lg border border-line overflow-hidden text-[14px]">
          <button
            v-for="t in (['active', 'history'] as const)"
            :key="t"
            class="px-3 py-1.5"
            :class="tab === t ? 'bg-brand-700 text-white font-semibold' : 'bg-surface text-ink-2'"
            @click="tab = t"
          >{{ t === 'active' ? '진행 중' : '이력' }}</button>
        </div>
        <select
          v-model="state"
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[14px]"
          @change="load"
        >
          <option value="">상태 전체</option>
          <option>RUNNING</option><option>PENDING</option>
          <option>COMPLETED</option><option>FAILED</option>
        </select>
        <input
          v-model="partition"
          placeholder="파티션"
          class="w-28 px-2.5 py-1.5 rounded-lg border border-line-dark text-[14px]"
          @keyup.enter="load"
        />
        <Fid id="U-JB-04" />
      </div>
    </template>

    <div v-if="loading" class="py-12 text-center text-ink-3 text-[14.5px]">불러오는 중…</div>
    <Empty v-else-if="!filtered.length" text="조건에 맞는 Job이 없습니다." />
    <Table v-else :columns="columns">
      <tr v-for="job in filtered" :key="jobId(job)" class="border-b border-line last:border-0 hover:bg-bg">
        <td class="px-3.5 py-2.5 mono">
          <RouterLink :to="`/jobs/${jobId(job)}`" class="text-brand-700 font-semibold">
            {{ jobId(job) }}
          </RouterLink>
        </td>
        <td class="px-3.5 py-2.5">{{ jobField(job, 'name') }}</td>
        <!--
          상태 칸은 상태만 보여준다. 대기 사유는 hover로 남긴다 — 한 칸에 몰아넣으면
          정작 상태가 안 읽힌다. 의존성 때문에 막힌 경우는 옆 칸이 따로 말해 준다.
        -->
        <td class="px-3.5 py-2.5">
          <span :title="waitReasonText(job) || undefined">
            <Badge :state="stateTone(jobState(job))">{{ jobState(job) || '—' }}</Badge>
          </span>
        </td>
        <!--
          앞 Job이 무엇인지 눌러서 갈 수 있어야 한다 — 번호만 적어 두면 사용자가
          목록을 다시 뒤져야 한다. 이름은 지금 목록에 있을 때만 덧붙인다(끝난 Job은
          Slurm이 잊기도 한다).
        -->
        <!-- 헤더 순서와 셀 순서를 같이 바꾼다 — 어긋나면 값이 옆 칸에 찍힌다. -->
        <template v-if="tab === 'history'">
          <td class="px-3.5 py-2.5 mono text-[13px]" :title="formatTimestampFull(jobStartedAt(job))">
            {{ formatTimestamp(jobStartedAt(job)) }}
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]" :title="formatTimestampFull(jobEndedAt(job))">
            {{ formatTimestamp(jobEndedAt(job)) }}
          </td>
          <td class="px-3.5 py-2.5 mono text-right">
            {{ formatDuration(jobElapsedSeconds(job, now)) }}
          </td>
        </template>
        <template v-else>
          <!-- 도는 중이면 **지금까지** 돈 시간이다. now가 1초마다 바뀌어 같이 흐른다. -->
          <td class="px-3.5 py-2.5 mono text-right">
            {{ formatDuration(jobElapsedSeconds(job, now)) }}
          </td>
          <td class="px-3.5 py-2.5">
          <span v-if="!jobDependency(job)" class="text-ink-3">—</span>
          <template v-else>
            <div v-for="(term, i) in parseDependency(jobDependency(job))" :key="i" class="text-[13px]">
              <span class="mono text-ink-3" :title="dependencyText(term.type)">{{ term.type }}</span>
              <template v-for="dep in term.jobs" :key="dep.id">
                <RouterLink
                  :to="`/jobs/${dep.id}`"
                  class="mono text-brand-700 font-semibold ml-1 hover:underline"
                >#{{ dep.id }}</RouterLink>
                <span v-if="nameOf(dep.id)" class="text-ink-2"> {{ nameOf(dep.id) }}</span>
                <span
                  v-if="dep.note"
                  class="text-[12px] ml-1"
                  :class="dep.note === 'failed' ? 'text-err font-semibold' : 'text-ink-3'"
                >({{ dependencyNoteText(dep.note) }})</span>
              </template>
            </div>
            <p v-if="isBlockedForever(job)" class="mt-1 text-[12px] text-err font-semibold">
              영원히 시작되지 않습니다 — 직접 취소해야 합니다
            </p>
          </template>
          </td>
        </template>
        <td class="px-3.5 py-2.5 mono">{{ jobField(job, 'partition') }}</td>
        <td class="px-3.5 py-2.5 mono">{{ jobField(job, 'account') }}</td>
        <td class="px-3.5 py-2.5 mono">{{ jobField(job, 'nodes') }}</td>
        <td class="px-3.5 py-2.5">
          <div class="flex gap-1.5">
            <Btn v-if="canCancel(job)" size="sm" variant="danger" @click="cancel(job)">취소</Btn>
            <Btn v-else size="sm" @click="resubmit(job)">재제출</Btn>
          </div>
        </td>
      </tr>
    </Table>

    <template #foot>
      Job 목록·취소는 <b>본인 소유</b>만 보입니다 — 서버가 범위를 강제합니다.
      <Fid id="U-JB-07" /> <Fid id="U-JB-08" /> <Fid id="U-JB-09" />
    </template>
  </Card>
</template>
