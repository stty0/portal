<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="비용 / Billing" :crumbs="['HPC Portal Admin', '운영']" sub="SCP 클라우드 청구 비용" />

  <div class="space-y-5">
    <Card title="비용 추이" flush>
      <template #title-extra><Fid id="A-BL-03" /></template>
      <NotImplemented api="GET /billing/trend" />
    </Card>
    <Card title="자원 식별 규칙" flush>
      <template #title-extra><Fid id="A-BL-02" /></template>
      <NotImplemented api="GET /billing/rules" />
    </Card>
    <Card title="SCP Billing API 연동" flush>
      <template #title-extra><Fid id="A-BL-01" /></template>
      <NotImplemented api="GET /billing/config" />
    </Card>
  </div>
</template>
