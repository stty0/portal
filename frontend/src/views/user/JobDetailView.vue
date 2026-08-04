<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import { jobField, jobState, stateTone } from '@/utils/job'
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
        <span class="text-[13px] text-ink-3">
          파티션 <b class="mono text-ink-2">{{ jobField(job, 'partition') }}</b>
        </span>
        <span class="text-[13px] text-ink-3">
          노드 <b class="mono text-ink-2">{{ jobField(job, 'nodes') }}</b>
        </span>
      </div>
      <dl class="grid grid-cols-[130px_1fr] gap-y-2 text-[13px]">
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
          class="mono text-[12px] bg-side-bg text-side-act rounded-lg p-4 overflow-x-auto whitespace-pre-wrap"
        >{{ jobField(job, 'script') }}</pre>
        <p v-else class="text-[13px] text-ink-3">이 Job에는 스크립트 정보가 없습니다.</p>
      </Card>

      <Card title="실시간 로그 (stdout / stderr)">
        <template #title-extra><Fid id="U-JB-06" /></template>
        <NotImplemented api="GET /clusters/{cid}/jobs/{id}/logs (SSE)" />
      </Card>
    </div>
  </div>
</template>
