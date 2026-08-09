<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import {
  dependencyNoteText, dependencyText, formatDuration, formatTimestamp,
  formatTimestampFull, isBlockedForever, isTerminal, jobDependency, jobElapsedSeconds,
  jobEndedAt, jobField, jobStartedAt, jobState, parseDependency, stateTone,
  waitReasonText,
} from '@/utils/job'
import type { SlurmJob } from '@/types/api'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'

const route = useRoute()
const router = useRouter()
const clusters = useClusterStore()

const job = ref<SlurmJob | null>(null)
const loading = ref(false)
const error = ref<unknown>(null)
const jobId = computed(() => String(route.params.jobId))

/** 도는 Job의 수행 시간이 멈춰 보이면 값이 틀린 것처럼 읽힌다 — 목록과 같은 태도. */
const now = ref(Math.floor(Date.now() / 1000))
let ticker: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  ticker = setInterval(() => {
    if (job.value && !isTerminal(job.value)) now.value = Math.floor(Date.now() / 1000)
  }, 1000)
})
onBeforeUnmount(() => clearInterval(ticker))

async function load() {
  if (!clusters.selectedId) return
  loading.value = true
  error.value = null
  try {
    job.value = await jobApi.get(clusters.selectedId, jobId.value)
  } catch (e) {
    error.value = e
    job.value = null
  } finally {
    loading.value = false
  }
}
watch([() => clusters.selectedId, jobId], load, { immediate: true })

async function cancel() {
  if (!clusters.selectedId || !confirm(`Job ${jobId.value} 을(를) 취소할까요?`)) return
  try {
    await jobApi.cancel(clusters.selectedId, jobId.value)
    router.push('/jobs')
  } catch (e) {
    error.value = e
  }
}

/** 상세는 slurmrestd가 준 필드를 전부 보여준다 — 스키마가 버전마다 달라 고정 목록이 위험하다. */
const rows = computed(() =>
  Object.entries(job.value ?? {})
    .filter(([, v]) => v !== null && v !== '' && typeof v !== 'object')
    .sort(([a], [b]) => a.localeCompare(b)),
)
</script>

<template>
  <PageHead
    :title="`Job #${jobId}`"
    :crumbs="['HPC Portal', 'Job', jobId]"
    :sub="job ? jobField(job, 'name') : clusters.selectedName"
  >
    <template #actions>
      <RouterLink to="/jobs"><Btn>목록으로</Btn></RouterLink>
      <!--
        Job ID는 제출해 봐야 알 수 있어서, 지금까지는 여기서 번호를 눈으로 읽어
        제출 폼에 손으로 옮겨야 했다. 그 한 칸을 없앤다 — 파이프라인을 만드는 것이
        아니라 Slurm이 이미 주는 기능(--dependency)에 닿는 길을 줄이는 것이다.
      -->
      <RouterLink :to="`/jobs/submit?dependency=afterok:${jobId}`">
        <Btn>이 Job 다음에 실행</Btn>
      </RouterLink>
      <Btn @click="load">↻ 새로고침</Btn>
      <Btn variant="danger" @click="cancel">Job 취소</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />
  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else-if="job" class="grid lg:grid-cols-2 gap-5 items-start">
    <Card title="상태 · 자원">
      <template #title-extra><Fid id="U-JB-05" /></template>
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <Badge :state="stateTone(jobState(job))">{{ jobState(job) || '—' }}</Badge>
        <span class="text-[14px] text-ink-3">
          파티션 <b class="mono text-ink-2">{{ jobField(job, 'partition') }}</b>
        </span>
        <span class="text-[14px] text-ink-3">
          노드 <b class="mono text-ink-2">{{ jobField(job, 'nodes') }}</b>
        </span>
      </div>
      <!--
        시간 필드는 `{set,infinite,number}` 래퍼라 아래 원문 목록에서 걸러진다
        (객체는 제외한다) — 그래서 상세에 시간이 하나도 안 보이고 있었다.
      -->
      <div class="flex flex-wrap gap-x-5 gap-y-1.5 mb-4 text-[14px] text-ink-3">
        <span :title="formatTimestampFull(jobStartedAt(job))">
          시작 <b class="mono text-ink-2">{{ formatTimestamp(jobStartedAt(job)) }}</b>
        </span>
        <span :title="formatTimestampFull(jobEndedAt(job))">
          종료 <b class="mono text-ink-2">{{ formatTimestamp(jobEndedAt(job)) }}</b>
        </span>
        <span>
          수행 시간 <b class="mono text-ink-2">{{ formatDuration(jobElapsedSeconds(job, now)) }}</b>
        </span>
      </div>
      <!--
        의존성과 대기 사유는 아래 원문 덤프에도 들어 있지만 알파벳순 목록에 묻힌다.
        "왜 안 도는가"에 답하는 값이라 위로 끌어올린다.
      -->
      <div
        v-if="waitReasonText(job) || jobDependency(job)"
        class="mb-4 px-3.5 py-3 rounded-lg text-[14px]"
        :class="isBlockedForever(job) ? 'bg-err-bg text-err' : 'bg-bg text-ink-2'"
      >
        <p v-if="waitReasonText(job)" :class="isBlockedForever(job) ? 'font-semibold' : ''">
          {{ waitReasonText(job) }}
        </p>
        <!-- 앞 Job으로 바로 갈 수 있어야 한다 — 번호만 적으면 목록을 다시 뒤져야 한다. -->
        <div v-if="jobDependency(job)" class="mt-1.5 text-[13.5px]">
          <div v-for="(term, i) in parseDependency(jobDependency(job))" :key="i">
            <span class="mono">{{ term.type }}</span>
            <span class="text-ink-3"> — {{ dependencyText(term.type) }}</span>
            <template v-for="dep in term.jobs" :key="dep.id">
              <RouterLink
                :to="`/jobs/${dep.id}`"
                class="mono font-semibold ml-2 underline"
              >#{{ dep.id }}</RouterLink>
              <span v-if="dep.note" class="text-[12.5px] ml-1">
                ({{ dependencyNoteText(dep.note) }})
              </span>
            </template>
          </div>
        </div>
        <p v-if="isBlockedForever(job)" class="mt-1.5 text-[13px]">
          Slurm이 이 Job을 자동으로 치우지 않습니다 — 직접 취소해야 큐에서 사라집니다.
        </p>
      </div>
      <dl class="grid grid-cols-[130px_1fr] gap-y-2 text-[14px]">
        <template v-for="[k, v] in rows" :key="k">
          <dt class="text-ink-3 mono truncate" :title="k">{{ k }}</dt>
          <dd class="text-ink-2 mono break-all">{{ v }}</dd>
        </template>
      </dl>
    </Card>

    <div class="space-y-5">
      <Card title="제출 스크립트">
        <pre
          v-if="jobField(job, 'script', '') !== ''"
          class="mono text-[13px] bg-side-bg text-side-act rounded-lg p-4 overflow-x-auto whitespace-pre-wrap"
        >{{ jobField(job, 'script') }}</pre>
        <p v-else class="text-[14px] text-ink-3">이 Job에는 스크립트 정보가 없습니다.</p>
      </Card>

      <Card title="실시간 로그 (stdout / stderr)">
        <template #title-extra><Fid id="U-JB-06" /></template>
        <NotImplemented api="GET /clusters/{cid}/jobs/{id}/logs (SSE)" />
      </Card>
    </div>
  </div>
</template>
