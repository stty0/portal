<script setup lang="ts">
import { ref, watch } from 'vue'
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

/** SCR-12 전체 Job 관리 — ADMIN은 모든 사용자의 Job을 보고 제어할 수 있다. */
const clusters = useClusterStore()
const jobs = ref<SlurmJob[]>([])
const loading = ref(false)
const error = ref<unknown>(null)
const username = ref('')
const state = ref('')

async function load() {
  if (!clusters.selectedId) return
  loading.value = true
  error.value = null
  try {
    const res = await jobApi.list(clusters.selectedId, {
      username: username.value || undefined,
      state: state.value || undefined,
    })
    jobs.value = res.items
  } catch (e) {
    error.value = e
    jobs.value = []
  } finally {
    loading.value = false
  }
}
watch(() => clusters.selectedId, load, { immediate: true })

async function control(job: SlurmJob, action: 'hold' | 'release') {
  if (!clusters.selectedId) return
  try {
    await jobApi.control(clusters.selectedId, jobId(job), action)
    await load()
  } catch (e) {
    error.value = e
  }
}

async function cancel(job: SlurmJob) {
  if (!clusters.selectedId || !confirm(`Job ${jobId(job)} (${jobField(job, 'user_name')}) 취소?`)) return
  try {
    await jobApi.cancel(clusters.selectedId, jobId(job))
    await load()
  } catch (e) {
    error.value = e
  }
}
</script>

<template>
  <PageHead
    title="전체 Job 관리"
    :crumbs="['HPC Portal Admin', '자원 관리', 'Job']"
    :sub="`${clusters.selectedName} · 모든 사용자 Job · 강제 제어`"
  >
    <template #actions><Btn @click="load">↻ 새로고침</Btn></template>
  </PageHead>

  <ErrorNote :error="error" />

  <Card flush>
    <template #head>
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="username" placeholder="사용자 ID"
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[13px] mono"
          @keyup.enter="load"
        />
        <select v-model="state" class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[13px]" @change="load">
          <option value="">상태 전체</option>
          <option>RUNNING</option><option>PENDING</option><option>COMPLETED</option><option>FAILED</option>
        </select>
        <Btn size="sm" @click="load">검색</Btn>
        <Fid id="A-JB-01" />
      </div>
    </template>

    <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>
    <Empty v-else-if="!jobs.length" text="조건에 맞는 Job이 없습니다." />
    <Table
      v-else
      :columns="[
        { key: 'i', label: 'Job ID', width: '110px' },
        { key: 'n', label: '이름' },
        { key: 'u', label: '사용자', width: '130px' },
        { key: 's', label: '상태', width: '110px' },
        { key: 'p', label: '파티션', width: '100px' },
        { key: 'a', label: '제어', width: '210px' },
      ]"
    >
      <tr v-for="job in jobs" :key="jobId(job)" class="border-b border-line last:border-0 hover:bg-bg">
        <td class="px-3.5 py-2.5 mono font-semibold">{{ jobId(job) }}</td>
        <td class="px-3.5 py-2.5">{{ jobField(job, 'name') }}</td>
        <td class="px-3.5 py-2.5 mono">{{ jobField(job, 'user_name') }}</td>
        <td class="px-3.5 py-2.5"><Badge :state="stateTone(jobState(job))">{{ jobState(job) || '—' }}</Badge></td>
        <td class="px-3.5 py-2.5 mono">{{ jobField(job, 'partition') }}</td>
        <td class="px-3.5 py-2.5">
          <div class="flex flex-wrap gap-1.5">
            <Btn size="sm" @click="control(job, 'hold')">Hold</Btn>
            <Btn size="sm" @click="control(job, 'release')">Release</Btn>
            <Btn size="sm" variant="danger" @click="cancel(job)">취소</Btn>
          </div>
        </td>
      </tr>
    </Table>

    <template #foot>
      모든 제어성 액션은 감사 로그에 기록됩니다. <Fid id="A-JB-02" /> <Fid id="A-JB-03" /> <Fid id="C-05" />
    </template>
  </Card>
</template>
