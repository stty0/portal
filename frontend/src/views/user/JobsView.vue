<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import { jobField, jobId, jobState, stateTone } from '@/utils/job'
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

const columns = [
  { key: 'id', label: 'Job ID', width: '110px' },
  { key: 'name', label: '이름' },
  { key: 'state', label: '상태', width: '110px' },
  { key: 'partition', label: '파티션', width: '110px' },
  { key: 'account', label: '계정', width: '120px' },
  { key: 'nodes', label: '노드', width: '120px' },
  { key: 'actions', label: '액션', width: '150px' },
]

async function load() {
  if (!clusters.selectedId) return
  loading.value = true
  error.value = null
  try {
    const filters = { state: state.value || undefined, partition: partition.value || undefined }
    const res =
      tab.value === 'active'
        ? await jobApi.list(clusters.selectedId, filters)
        : await jobApi.history(clusters.selectedId, {})
    jobs.value = res.items
  } catch (e) {
    error.value = e
    jobs.value = []
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

const canCancel = (job: SlurmJob) => ['running', 'pending'].includes(stateTone(jobState(job)))
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

  <Card flush>
    <template #head>
      <div class="flex flex-wrap items-center gap-2">
        <div class="flex rounded-lg border border-line overflow-hidden text-[13px]">
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
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[13px]"
          @change="load"
        >
          <option value="">상태 전체</option>
          <option>RUNNING</option><option>PENDING</option>
          <option>COMPLETED</option><option>FAILED</option>
        </select>
        <input
          v-model="partition"
          placeholder="파티션"
          class="w-28 px-2.5 py-1.5 rounded-lg border border-line-dark text-[13px]"
          @keyup.enter="load"
        />
        <Fid id="U-JB-04" />
      </div>
    </template>

    <div v-if="loading" class="py-12 text-center text-ink-3 text-[13.5px]">불러오는 중…</div>
    <Empty v-else-if="!filtered.length" text="조건에 맞는 Job이 없습니다." />
    <Table v-else :columns="columns">
      <tr v-for="job in filtered" :key="jobId(job)" class="border-b border-line last:border-0 hover:bg-bg">
        <td class="px-3.5 py-2.5 mono">
          <RouterLink :to="`/jobs/${jobId(job)}`" class="text-brand-700 font-semibold">
            {{ jobId(job) }}
          </RouterLink>
        </td>
        <td class="px-3.5 py-2.5">{{ jobField(job, 'name') }}</td>
        <td class="px-3.5 py-2.5">
          <Badge :state="stateTone(jobState(job))">{{ jobState(job) || '—' }}</Badge>
        </td>
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
