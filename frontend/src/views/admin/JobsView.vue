<script setup lang="ts">
import { ref, watch } from 'vue'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import { canCancel, canHold, isTerminal, jobField, jobId, jobOwner, jobState, stateTone } from '@/utils/job'
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
const tab = ref<'active' | 'history'>('active')
/** 이력 출처. slurmdbd가 끊기면 slurmctld의 잔여 완료 Job으로 대체된다. */
const source = ref<string | null>(null)

async function load() {
  if (!clusters.selectedId) return
  loading.value = true
  error.value = null
  try {
    // 이력은 slurmdbd(sacct 상당)에서 온다 — 진행 중 목록(slurmctld)과 출처가 다르다.
    const res =
      tab.value === 'active'
        ? await jobApi.list(clusters.selectedId, {
            username: username.value || undefined,
            state: state.value || undefined,
          })
        : await jobApi.history(clusters.selectedId, {
            username: username.value || undefined,
            state: state.value || undefined,
          })
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
  if (!clusters.selectedId || !confirm(`Job ${jobId(job)} (${jobOwner(job)}) 취소?`)) return
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

  <!-- 이력이 slurmdbd가 아니라 slurmctld에서 온 경우, 목록이 불완전함을 밝힌다 -->
  <div
    v-if="source === 'slurmctld'"
    class="mb-3 px-3.5 py-2.5 rounded-lg bg-warn-bg text-warn text-[14px]"
  >
    slurmdbd에 연결할 수 없어 <b>최근 완료된 Job만</b> 표시합니다.
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
        <input
          v-model="username" placeholder="사용자 ID"
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[14px] mono"
          @keyup.enter="load"
        />
        <select
          v-model="state"
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[14px]"
          @change="load"
        >
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
        <td class="px-3.5 py-2.5 mono">{{ jobOwner(job) }}</td>
        <td class="px-3.5 py-2.5"><Badge :state="stateTone(jobState(job))">{{ jobState(job) || '—' }}</Badge></td>
        <td class="px-3.5 py-2.5 mono">{{ jobField(job, 'partition') }}</td>
        <td class="px-3.5 py-2.5">
          <!-- 끝난 Job에는 제어가 의미 없다. Hold/Release는 대기 중에만 가능하다. -->
          <div v-if="!isTerminal(job)" class="flex flex-wrap gap-1.5">
            <template v-if="canHold(job)">
              <Btn size="sm" @click="control(job, 'hold')">Hold</Btn>
              <Btn size="sm" @click="control(job, 'release')">Release</Btn>
            </template>
            <Btn v-if="canCancel(job)" size="sm" variant="danger" @click="cancel(job)">취소</Btn>
          </div>
          <span v-else class="text-ink-3">—</span>
        </td>
      </tr>
    </Table>

    <template #foot>
      모든 제어성 액션은 감사 로그에 기록됩니다. <Fid id="A-JB-02" /> <Fid id="A-JB-03" /> <Fid id="C-05" />
    </template>
  </Card>
</template>
