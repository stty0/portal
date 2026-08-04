<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="통계 / 리포트" :crumbs="['HPC Portal Admin', '운영']" sub="기간별 사용량·가동률·대기시간" />

  <div class="space-y-5">
    <Card title="사용량 리포트" flush>
      <template #title-extra><Fid id="A-RP-01" /></template>
      <NotImplemented api="GET /clusters/{cid}/reports/usage" />
    </Card>
    <Card title="가동률 추이" flush>
      <template #title-extra><Fid id="A-RP-02" /></template>
      <NotImplemented api="GET /clusters/{cid}/reports/utilization" />
    </Card>
    <Card title="대기시간 분석" flush>
      <template #title-extra><Fid id="A-RP-03" /></template>
      <NotImplemented api="GET /clusters/{cid}/reports/wait-time" />
    </Card>
  </div>
</template>
