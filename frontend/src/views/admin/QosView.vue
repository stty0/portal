<script setup lang="ts">
import { ref, watch } from 'vue'
import { clusterApi, type SlurmQos } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'
import { inputClass } from '@/utils/form'

/** SCR-13 QOS — slurmdbd의 QOS 정의를 읽고 만든다 (A-US-03). */
const clusters = useClusterStore()
const rows = ref<SlurmQos[]>([])
const loading = ref(false)
const busy = ref(false)
const error = ref<unknown>(null)
const form = ref({
  name: '',
  description: '',
  priority: null as number | null,
  max_wall_minutes: null as number | null,
  max_jobs_per_user: null as number | null,
})

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  error.value = null
  try {
    rows.value = await clusterApi.qos(cid)
  } catch (e) {
    error.value = e
    rows.value = []
  } finally {
    loading.value = false
  }
}
watch(() => clusters.selectedId, load, { immediate: true })

async function create() {
  const cid = clusters.selectedId
  if (!cid || !form.value.name) return
  busy.value = true
  error.value = null
  try {
    await clusterApi.createQos(cid, { ...form.value })
    form.value = {
      name: '',
      description: '',
      priority: null,
      max_wall_minutes: null,
      max_jobs_per_user: null,
    }
    await load()
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

async function remove(name: string) {
  const cid = clusters.selectedId
  if (!cid || !confirm(`QOS '${name}'을(를) 삭제할까요?`)) return
  busy.value = true
  error.value = null
  try {
    await clusterApi.deleteQos(cid, name)
    await load()
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

/** 제한값이 비어 있으면 무제한이다 — 0과 구분되어야 한다. */
const limit = (v: number | null, unit = '') => (v === null ? '무제한' : `${v}${unit}`)
</script>

<template>
  <PageHead
    title="QOS 정책"
    :crumbs="['HPC Portal Admin', '사용자 / 정책']"
    :sub="`QOS 정의 · ${clusters.selectedName}`"
  >
    <template #actions><Btn @click="load">↻ 새로고침</Btn></template>
  </PageHead>

  <div class="space-y-5">
    <Card title="QOS 정책" flush>
      <template #title-extra><Fid id="A-US-03" /></template>
      <template #head><Chip tone="gray">{{ rows.length }}개</Chip></template>
      <ErrorNote :error="error" class="m-4" />

      <form class="px-4 py-3 border-b border-line flex flex-wrap gap-2 items-end" @submit.prevent="create">
        <label class="flex-1 min-w-[140px] text-[13px] text-ink-3">
          이름*
          <input v-model="form.name" required pattern="[A-Za-z0-9._-]+" :class="[inputClass, 'mono mt-1']" placeholder="short" />
        </label>
        <label class="flex-[2] min-w-[160px] text-[13px] text-ink-3">
          설명
          <input v-model="form.description" :class="[inputClass, 'mt-1']" />
        </label>
        <label class="w-28 text-[13px] text-ink-3">
          우선순위
          <input v-model.number="form.priority" type="number" min="0" :class="[inputClass, 'mono mt-1']" />
        </label>
        <label class="w-32 text-[13px] text-ink-3">
          최대 실행(분)
          <input v-model.number="form.max_wall_minutes" type="number" min="1" :class="[inputClass, 'mono mt-1']" />
        </label>
        <label class="w-32 text-[13px] text-ink-3">
          사용자당 Job
          <input v-model.number="form.max_jobs_per_user" type="number" min="1" :class="[inputClass, 'mono mt-1']" />
        </label>
        <Btn type="submit" variant="primary" :disabled="busy">QOS 추가</Btn>
      </form>

      <div v-if="loading" class="py-10 text-center text-ink-3">불러오는 중…</div>
      <Empty v-else-if="!rows.length" text="정의된 QOS가 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: 'QOS', width: '160px' },
          { key: 'desc', label: '설명' },
          { key: 'prio', label: '우선순위', num: true },
          { key: 'wall', label: '최대 실행', num: true },
          { key: 'jobs', label: '사용자당 Job', num: true },
          { key: 'factor', label: '사용 계수', num: true },
          { key: 'act', label: '', width: '90px' },
        ]"
      >
        <tr v-for="q in rows" :key="q.name" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ q.name }}</td>
          <td class="px-3.5 py-2.5 text-ink-3">{{ q.description || '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ q.priority ?? 0 }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ limit(q.max_wall_minutes, '분') }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ limit(q.max_jobs_per_user) }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ q.usage_factor ?? '—' }}</td>
          <td class="px-3.5 py-2.5">
            <!-- normal은 Slurm 기본 QOS라 삭제 대상이 아니다 -->
            <Btn v-if="q.name !== 'normal'" size="sm" variant="danger" :disabled="busy" @click="remove(q.name)">
              삭제
            </Btn>
            <span v-else class="text-ink-3 text-[13px]">기본</span>
          </td>
        </tr>
      </Table>
      <template #foot>
        빈 제한값은 <b>무제한</b>입니다. 변경은 감사 로그에 기록되며, 클러스터의
        <span class="mono">sacctmgr</span>와 같은 대상을 다룹니다.
      </template>
    </Card>
  </div>
</template>
