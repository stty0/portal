<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { clusterApi } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import { num, numText, resourceTone, states, text, type SlurmRecord } from '@/utils/slurm'
import Table from '@/components/ui/Table.vue'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'

/**
 * SCR-02 — 선택 클러스터의 파티션별 가용 자원(U-CL-02).
 * 클러스터 선택은 톱바 선택기가, 공지(U-CL-03)는 톱바 공지 메뉴가 맡는다.
 */
const clusters = useClusterStore()
const error = ref<unknown>(null)

// 클러스터 선택은 톱바가 한다. 여기서는 아래 watch가 볼 selectedId가 정해지도록 목록만 채운다.
onMounted(async () => {
  if (clusters.loaded) return
  try {
    await clusters.load()
  } catch (e) {
    error.value = e
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
    sub="선택한 클러스터의 파티션별 가용 자원"
  >
    <template #actions>
      <RouterLink to="/jobs/submit"><Btn variant="primary">＋ Job 제출</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

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
</template>
