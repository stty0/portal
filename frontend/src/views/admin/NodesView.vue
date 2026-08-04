<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
import { useClusterStore } from '@/stores/cluster'

const clusters = useClusterStore()
</script>

<template>
  <PageHead title="노드 / 파티션 관리" :crumbs="['HPC Portal Admin', '자원 관리']" :sub="`노드 상태 제어와 파티션 구성 · ${clusters.selectedName}`" />

  <div class="space-y-5">
    <Card title="노드" flush>
      <template #title-extra><Fid id="A-ND-02" /></template>
      <NotImplemented api="GET /clusters/{cid}/nodes" />
    </Card>
    <Card title="파티션" flush>
      <template #title-extra><Fid id="A-ND-03" /></template>
      <NotImplemented api="GET /clusters/{cid}/partitions" />
    </Card>
    <Card title="예약" flush>
      <template #title-extra><Fid id="A-ND-04" /></template>
      <NotImplemented api="GET /clusters/{cid}/reservations" />
    </Card>
  </div>
</template>
