<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
import { useClusterStore } from '@/stores/cluster'

const clusters = useClusterStore()
</script>

<template>
  <PageHead title="웹 터미널" :crumbs="['HPC Portal', '작업 환경']" :sub="`로그인 노드 셸 (SSH PTY) · ${clusters.selectedName}`" />

  <div class="space-y-5">
    <Card title="터미널" flush>
      <template #title-extra><Fid id="U-SH-01" /></template>
      <NotImplemented api="WS /clusters/{cid}/terminal" />
    </Card>
  </div>
</template>
