<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { clusterApi } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import { num, numText, resourceTone, states, text, type SlurmRecord } from '@/utils/slurm'
import ResourceUsage from '@/components/ui/ResourceUsage.vue'
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

/**
 * 파티션 안의 노드. 백엔드가 **사용자에게 필요한 필드만** 추려 실어 준다.
 * 사용량은 파티션 요약과 **같은 모양**이라 같은 컬럼·같은 컴포넌트로 그린다.
 */
interface PartitionNode {
  name: string
  state: string[]
  cpu_usage: SlurmRecord
  memory_usage: SlurmRecord
  gpu_usage: SlurmRecord
  gres: string
}

const nodesOf = (row: SlurmRecord): PartitionNode[] =>
  (row.node_list as PartitionNode[] | undefined) ?? []

/**
 * 펼친 파티션. **하나만 연다** — 여러 개를 동시에 펼치면 표가 길어져 정작 파티션 비교가
 * 안 된다(이 화면의 목적은 "어느 파티션에 자리가 있나"다).
 */
const expanded = ref<string | null>(null)
const toggle = (name: string) => {
  expanded.value = expanded.value === name ? null : name
}

/** MB → GB. 노드 목록과 파티션 요약이 **같은 표기**를 써야 눈이 헷갈리지 않는다. */
const gb = (mb: number) => (mb ? `${(mb / 1024).toFixed(1)}GB` : '0')

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
        { key: 'cpu', label: 'CPU (사용/가용/전체)', num: true },
        { key: 'mem', label: '메모리 (사용/가용/전체)', num: true },
        { key: 'gpu', label: 'GPU (사용/가용/전체)', num: true },
        { key: 'time', label: '최대 실행시간', num: true },
      ]"
    >
      <!-- 사용 중/가용은 노드를 파티션별로 더한 값이다(파티션 응답에는 총량만 온다).
           빠져 있는(DOWN·DRAIN) 노드의 CPU는 어느 쪽에도 안 들어가 합이 전체보다 작을 수 있다. -->
      <!-- 행 두 개(요약 + 펼친 노드)가 한 파티션이라 template으로 묶는다. -->
      <template v-for="p in partitions" :key="String(p.name)">
      <tr
        class="border-b border-line last:border-0 cursor-pointer hover:bg-bg"
        @click="toggle(text(p, 'name'))"
      >
        <td class="px-3.5 py-2.5 mono font-semibold">
          <!-- 펼침은 키보드로도 되어야 한다 — 행 클릭은 마우스 편의일 뿐이다. -->
          <button
            type="button"
            class="flex items-center gap-1.5 text-left"
            :aria-expanded="expanded === text(p, 'name')"
            @click.stop="toggle(text(p, 'name'))"
          >
            <span
              class="text-ink-3 transition-transform"
              :class="expanded === text(p, 'name') ? 'rotate-90' : ''"
            >›</span>
            {{ text(p, 'name') }}
          </button>
        </td>
        <td class="px-3.5 py-2.5">
          <Badge v-for="s in states(sub(p, 'partition'))" :key="s" :state="resourceTone(s)">
            {{ s }}
          </Badge>
        </td>
        <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'nodes').total) ?? '—' }}</td>
        <!--
          자원마다 칸을 하나씩 쓴다. 셋을 각각 세 칸으로 벌리면 아홉 칸이 되어 정작
          파티션 비교가 안 된다 — **가용을 굵게** 해서 "자리가 있나"가 먼저 읽히게 한다.
        -->
        <td class="px-3.5 py-2.5 mono text-right whitespace-nowrap">
          <ResourceUsage :usage="sub(p, 'cpu_usage')" />
        </td>
        <td class="px-3.5 py-2.5 mono text-right whitespace-nowrap">
          <ResourceUsage :usage="sub(p, 'memory_usage')" :format="gb" />
        </td>
        <td class="px-3.5 py-2.5 mono text-right whitespace-nowrap">
          <ResourceUsage :usage="sub(p, 'gpu_usage')" />
        </td>
        <td class="px-3.5 py-2.5 mono text-right">{{ numText(sub(p, 'maximums').time, '분') }}</td>
      </tr>
      <!--
        노드 목록. 파티션 표의 컬럼과 폭이 다르므로 **한 칸을 통째로 쓰고** 그 안에 따로 그린다 —
        같은 표에 억지로 맞추면 두 표가 서로의 폭을 흔든다.
      -->
      <!--
        노드는 **파티션과 같은 컬럼에 그린다.** 따로 표를 만들면 열이 어긋나서 같은 값을
        위아래로 비교할 수 없다 — 펼치는 이유가 그 비교인데.
      -->
      <tr
        v-for="n in nodesOf(p)"
        v-show="expanded === text(p, 'name')"
        :key="`${p.name}-${n.name}`"
        class="border-b border-line bg-bg"
      >
        <td class="px-3.5 py-2 mono text-[13.5px] text-ink-2">
          <span class="text-line-dark mr-1.5">└</span>{{ n.name }}
          <span v-if="n.gres" class="ml-2 text-[12px] text-ink-3">{{ n.gres }}</span>
        </td>
        <td class="px-3.5 py-2">
          <Badge v-for="st in n.state" :key="st" :state="resourceTone(st)" class="mr-1">
            {{ st }}
          </Badge>
        </td>
        <td class="px-3.5 py-2"></td>
        <td class="px-3.5 py-2 mono text-right text-[13.5px] whitespace-nowrap">
          <ResourceUsage :usage="n.cpu_usage" />
        </td>
        <td class="px-3.5 py-2 mono text-right text-[13.5px] whitespace-nowrap">
          <ResourceUsage :usage="n.memory_usage" :format="gb" />
        </td>
        <td class="px-3.5 py-2 mono text-right text-[13.5px] whitespace-nowrap">
          <ResourceUsage :usage="n.gpu_usage" />
        </td>
        <td class="px-3.5 py-2"></td>
      </tr>
      <tr v-if="expanded === text(p, 'name') && !nodesOf(p).length" class="border-b border-line bg-bg">
        <td colspan="7" class="px-3.5 py-2 text-[13.5px] text-ink-3">
          이 파티션의 노드 정보를 읽지 못했습니다.
        </td>
      </tr>
      </template>
    </Table>
  </Card>
</template>
