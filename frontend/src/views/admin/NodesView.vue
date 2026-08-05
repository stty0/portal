<script setup lang="ts">
import { ref, watch } from 'vue'
import { clusterApi } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import { mib, num, numText, resourceTone, states, text, type SlurmRecord } from '@/utils/slurm'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-11 — 노드·파티션·예약을 slurmrestd에서 조회한다(A-ND-02·03·04). 아직 조회 전용이다. */
const clusters = useClusterStore()
const nodes = ref<SlurmRecord[]>([])
const partitions = ref<SlurmRecord[]>([])
const reservations = ref<SlurmRecord[]>([])
const loading = ref(false)
/**
 * 오류는 패널별로 따로 잡는다.
 * 세 조회는 서로 독립인데 하나로 묶으면(Promise.all) 한쪽 실패가 나머지 성공분까지 버린다.
 * 실제로 slurmdbd가 끊기면 slurmrestd가 파티션 조회에만 500을 돌려주는 상황이 있다.
 */
const errors = ref<Record<'nodes' | 'partitions' | 'reservations', unknown>>({
  nodes: null,
  partitions: null,
  reservations: null,
})

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [n, p, r] = await Promise.allSettled([
    clusterApi.nodes(cid),
    clusterApi.partitions(cid),
    clusterApi.reservations(cid),
  ])
  nodes.value = n.status === 'fulfilled' ? n.value : []
  partitions.value = p.status === 'fulfilled' ? p.value : []
  reservations.value = r.status === 'fulfilled' ? r.value : []
  errors.value = {
    nodes: n.status === 'rejected' ? n.reason : null,
    partitions: p.status === 'rejected' ? p.reason : null,
    reservations: r.status === 'rejected' ? r.reason : null,
  }
  loading.value = false
}
watch(() => clusters.selectedId, load, { immediate: true })

function cpuText(n: SlurmRecord): string {
  const total = num(n.cpus)
  return total === null ? '—' : `${num(n.alloc_cpus) ?? 0} / ${total}`
}

function memText(n: SlurmRecord): string {
  return num(n.real_memory) === null ? '—' : `${mib(n.alloc_memory)} / ${mib(n.real_memory)}`
}

const sub = (row: SlurmRecord, key: string): SlurmRecord =>
  (row[key] as SlurmRecord | undefined) ?? {}
</script>

<template>
  <PageHead
    title="노드 / 파티션 관리"
    :crumbs="['HPC Portal Admin', '자원 관리']"
    :sub="`노드 상태와 파티션 구성 · ${clusters.selectedName}`"
  >
    <template #actions><Btn @click="load">↻ 새로고침</Btn></template>
  </PageHead>

  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="노드" flush>
      <template #title-extra><Fid id="A-ND-02" /></template>
      <ErrorNote :error="errors.nodes" class="m-4" />
      <Empty v-if="!nodes.length && !errors.nodes" text="노드가 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '노드' },
          { key: 'state', label: '상태' },
          { key: 'part', label: '파티션' },
          { key: 'cpu', label: 'CPU (할당/전체)', num: true },
          { key: 'mem', label: '메모리 (할당/전체)', num: true },
          { key: 'load', label: 'CPU Load', num: true },
          { key: 'gres', label: 'GRES' },
          { key: 'reason', label: '사유' },
        ]"
      >
        <tr v-for="n in nodes" :key="String(n.name)" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(n, 'name') }}</td>
          <td class="px-3.5 py-2.5">
            <span class="flex flex-wrap gap-1">
              <Badge v-for="s in states(n)" :key="s" :state="resourceTone(s)">{{ s }}</Badge>
            </span>
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(n, 'partitions') }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ cpuText(n) }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ memText(n) }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(n.cpu_load) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(n, 'gres') }}</td>
          <td class="px-3.5 py-2.5 text-[13px] text-ink-3">{{ text(n, 'reason') }}</td>
        </tr>
      </Table>
    </Card>

    <Card title="파티션" flush>
      <template #title-extra><Fid id="A-ND-03" /></template>
      <ErrorNote :error="errors.partitions" class="m-4" />
      <Empty v-if="!partitions.length && !errors.partitions" text="파티션이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '파티션' },
          { key: 'state', label: '상태' },
          { key: 'nodes', label: '노드' },
          { key: 'cnt', label: '노드 수', num: true },
          { key: 'cpus', label: 'CPU', num: true },
          { key: 'time', label: '최대 실행시간', num: true },
          { key: 'prio', label: '우선순위', num: true },
        ]"
      >
        <tr v-for="p in partitions" :key="String(p.name)" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(p, 'name') }}</td>
          <td class="px-3.5 py-2.5">
            <Badge v-for="s in states(sub(p, 'partition'))" :key="s" :state="resourceTone(s)">
              {{ s }}
            </Badge>
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(sub(p, 'nodes'), 'configured') }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'nodes').total) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'cpus').total) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">
            {{ numText(sub(p, 'maximums').time, '분') }}
          </td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'priority').tier) ?? '—' }}</td>
        </tr>
      </Table>
    </Card>

    <Card title="예약" flush>
      <template #title-extra><Fid id="A-ND-04" /></template>
      <ErrorNote :error="errors.reservations" class="m-4" />
      <Empty v-if="!reservations.length && !errors.reservations" text="예약이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '예약명' },
          { key: 'nodes', label: '노드' },
          { key: 'users', label: '사용자' },
          { key: 'accounts', label: '계정' },
          { key: 'start', label: '시작', num: true },
          { key: 'end', label: '종료', num: true },
        ]"
      >
        <tr
          v-for="r in reservations"
          :key="String(r.name)"
          class="border-b border-line last:border-0"
        >
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(r, 'name') }}</td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(r, 'node_list') }}</td>
          <td class="px-3.5 py-2.5 text-[13px]">{{ text(r, 'users') }}</td>
          <td class="px-3.5 py-2.5 text-[13px]">{{ text(r, 'accounts') }}</td>
          <td class="px-3.5 py-2.5 mono text-right text-[13px]">{{ numText(r.start_time) }}</td>
          <td class="px-3.5 py-2.5 mono text-right text-[13px]">{{ numText(r.end_time) }}</td>
        </tr>
      </Table>
    </Card>
  </div>
</template>
