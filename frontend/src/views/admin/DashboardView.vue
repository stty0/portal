<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import { jobState, stateTone } from '@/utils/job'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'

/**
 * SCR-10 대시보드.
 * Job 통계는 실 API로 계산한다. 노드 맵·부하 시계열·이벤트·스토리지는 백엔드 미구현이라
 * 값을 지어내지 않고 비워 둔다 — 가짜 숫자는 운영 판단을 틀리게 만든다.
 */
const clusters = useClusterStore()
const error = ref<unknown>(null)
const loading = ref(false)
const counts = ref({ total: 0, running: 0, pending: 0, failed: 0 })

async function load() {
  if (!clusters.selectedId) return
  loading.value = true
  error.value = null
  try {
    const res = await jobApi.list(clusters.selectedId)
    const tally = { total: res.items.length, running: 0, pending: 0, failed: 0 }
    for (const job of res.items) {
      const tone = stateTone(jobState(job))
      if (tone === 'running') tally.running++
      else if (tone === 'pending') tally.pending++
      else if (tone === 'failed') tally.failed++
    }
    counts.value = tally
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => clusters.selectedId, load)
</script>

<template>
  <PageHead
    title="대시보드"
    :crumbs="['HPC Portal Admin', '모니터링']"
    :sub="`${clusters.selectedName} · 클러스터 현황 요약`"
  >
    <template #actions>
      <Btn @click="load">↻ 새로고침</Btn>
      <RouterLink to="/admin/jobs"><Btn variant="primary">☰ 전체 Job</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <Card title="Job 현황" class="mb-5">
    <template #title-extra><Fid id="A-DB-03" /></template>
    <div v-if="loading" class="py-6 text-center text-ink-3 text-[14.5px]">불러오는 중…</div>
    <div v-else class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="s in [
          { k: '전체', v: counts.total, tone: 'text-ink' },
          { k: 'Running', v: counts.running, tone: 'text-info' },
          { k: 'Pending', v: counts.pending, tone: 'text-warn' },
          { k: 'Failed', v: counts.failed, tone: 'text-err' },
        ]"
        :key="s.k"
      >
        <p class="text-[13.5px] text-ink-3 mb-1">{{ s.k }}</p>
        <p class="text-[32px] font-bold mono" :class="s.tone">{{ s.v }}</p>
      </div>
    </div>
  </Card>

  <div class="grid lg:grid-cols-2 gap-5 items-start">
    <Card title="노드 상태 맵" flush>
      <template #title-extra><Fid id="A-DB-01" /></template>
      <NotImplemented api="GET /clusters/{cid}/nodes" />
    </Card>
    <Card title="실시간 부하" flush>
      <template #title-extra><Fid id="A-DB-02" /></template>
      <NotImplemented api="GET /clusters/{cid}/metrics" />
    </Card>
    <Card title="최근 이벤트" flush>
      <template #title-extra><Fid id="A-DB-04" /></template>
      <NotImplemented api="GET /clusters/{cid}/events" />
    </Card>
    <Card title="스토리지 현황" flush>
      <template #title-extra><Fid id="A-DB-05" /></template>
      <NotImplemented api="GET /clusters/{cid}/storage" />
    </Card>
  </div>
</template>
