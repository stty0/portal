<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="License 관리" :crumbs="['HPC Portal Admin', '운영']" sub="FlexNet/FlexLM 서버 연동" />

  <div class="space-y-5">
    <Card title="라이선스 서버" flush>
      <template #title-extra><Fid id="A-LM-01" /></template>
      <NotImplemented api="GET /license/servers" />
    </Card>
    <Card title="Feature 사용 현황" flush>
      <template #title-extra><Fid id="A-LM-02" /></template>
      <NotImplemented api="GET /license/features" />
    </Card>
  </div>
</template>
