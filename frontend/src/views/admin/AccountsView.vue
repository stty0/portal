<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
import { useClusterStore } from '@/stores/cluster'

const clusters = useClusterStore()
</script>

<template>
  <PageHead title="계정 (Account)" :crumbs="['HPC Portal Admin', '사용자 / 정책']" :sub="`Slurm 계정과 사용자 매핑 · ${clusters.selectedName}`" />

  <div class="space-y-5">
    <Card title="계정 목록" flush>
      <template #title-extra><Fid id="A-US-02" /></template>
      <NotImplemented api="GET /clusters/{cid}/accounts" />
    </Card>
  </div>
</template>
