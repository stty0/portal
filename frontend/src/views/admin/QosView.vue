<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
import { useClusterStore } from '@/stores/cluster'

const clusters = useClusterStore()
</script>

<template>
  <PageHead title="QOS 정책" :crumbs="['HPC Portal Admin', '사용자 / 정책']" :sub="`QOS 정의 · 자원 신청 승인 · ${clusters.selectedName}`" />

  <div class="space-y-5">
    <Card title="QOS 정책" flush>
      <template #title-extra><Fid id="A-US-03" /></template>
      <NotImplemented api="GET /clusters/{cid}/qos" />
    </Card>
    <Card title="자원 신청 승인" flush>
      <template #title-extra><Fid id="A-US-06" /></template>
      <NotImplemented api="미설계 — 정의서 선택 기능" />
    </Card>
  </div>
</template>
