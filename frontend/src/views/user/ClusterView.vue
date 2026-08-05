<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { clusterApi } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import { num, numText, resourceTone, states, text, type SlurmRecord } from '@/utils/slurm'
import Table from '@/components/ui/Table.vue'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'

/** SCR-02 — 클러스터 목록은 실 API. 파티션·자원 현황은 백엔드 미구현이라 비워 둔다. */
const clusters = useClusterStore()
const error = ref<unknown>(null)
const loading = ref(false)

onMounted(async () => {
  if (clusters.loaded) return
  loading.value = true
  try {
    await clusters.load()
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
})

/** 파티션 현황(U-CL-02)은 선택 클러스터에 종속된다 — 클러스터를 바꾸면 다시 읽는다. */
const partitions = ref<SlurmRecord[]>([])
const partLoading = ref(false)
const sub = (row: SlurmRecord, key: string): SlurmRecord =>
  (row[key] as SlurmRecord | undefined) ?? {}

watch(
  () => clusters.selectedId,
  async (cid) => {
    if (!cid) return
    partLoading.value = true
    try {
      partitions.value = await clusterApi.partitions(cid)
    } catch {
      // 파티션 조회 실패가 클러스터 목록 화면 전체를 막지 않게 한다.
      partitions.value = []
    } finally {
      partLoading.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <PageHead
    title="클러스터"
    :crumbs="['HPC Portal', '클러스터']"
    sub="등록된 클러스터 상태와 가용 자원"
  >
    <template #actions>
      <RouterLink to="/jobs/submit"><Btn variant="primary">＋ Job 제출</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <Card title="등록된 클러스터" class="mb-5">
    <template #title-extra><Fid id="U-CL-01" /></template>
    <div v-if="loading" class="py-10 text-center text-ink-3 text-[14.5px]">불러오는 중…</div>
    <Empty v-else-if="!clusters.clusters.length" text="등록된 클러스터가 없습니다." />
    <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="c in clusters.clusters"
        :key="c.id"
        class="border border-line rounded-lg p-4"
        :class="c.id === clusters.selectedId ? 'border-brand-500 bg-brand-50' : ''"
      >
        <div class="flex items-start gap-2 mb-2.5">
          <div class="flex-1 min-w-0">
            <b class="block text-[15.5px] text-ink truncate">{{ c.description || c.name }}</b>
            <code class="text-[13px] text-ink-3 mono">{{ c.name }}</code>
          </div>
          <Badge :state="c.is_active ? 'idle' : 'down'">{{ c.is_active ? '정상' : '중지' }}</Badge>
        </div>
        <div class="flex gap-1.5 mb-3">
          <Chip v-if="c.is_default" tone="brand">기본</Chip>
          <Chip v-if="c.id === clusters.selectedId" tone="cluster">선택됨</Chip>
        </div>
        <Btn v-if="c.id !== clusters.selectedId" size="sm" class="w-full" @click="clusters.select(c.id)">
          이 클러스터 선택
        </Btn>
      </div>
    </div>
  </Card>

  <div class="grid lg:grid-cols-2 gap-5 items-start">
    <Card title="파티션별 가용 자원" flush>
      <template #title-extra><Fid id="U-CL-02" /></template>
      <Empty v-if="!partitions.length" :text="partLoading ? '불러오는 중…' : '파티션 정보가 없습니다.'" />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '파티션' },
          { key: 'state', label: '상태' },
          { key: 'nodes', label: '노드 수', num: true },
          { key: 'cpus', label: 'CPU', num: true },
          { key: 'time', label: '최대 실행시간', num: true },
        ]"
      >
        <tr v-for="p in partitions" :key="String(p.name)" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(p, 'name') }}</td>
          <td class="px-3.5 py-2.5">
            <Badge v-for="s in states(sub(p, 'partition'))" :key="s" :state="resourceTone(s)">
              {{ s }}
            </Badge>
          </td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'nodes').total) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'cpus').total) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ numText(sub(p, 'maximums').time, '분') }}</td>
        </tr>
      </Table>
    </Card>
    <Card title="공지사항" flush>
      <template #title-extra><Fid id="U-CL-03" /></template>
      <NotImplemented api="GET /notices" />
    </Card>
  </div>
</template>
