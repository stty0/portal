<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useClusterStore } from '@/stores/cluster'
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
    <div v-if="loading" class="py-10 text-center text-ink-3 text-[13.5px]">불러오는 중…</div>
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
            <b class="block text-[14.5px] text-ink truncate">{{ c.description || c.name }}</b>
            <code class="text-[12px] text-ink-3 mono">{{ c.name }}</code>
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
      <NotImplemented api="GET /clusters/{cid}/partitions" />
    </Card>
    <Card title="공지사항" flush>
      <template #title-extra><Fid id="U-CL-03" /></template>
      <NotImplemented api="GET /notices" />
    </Card>
  </div>
</template>
