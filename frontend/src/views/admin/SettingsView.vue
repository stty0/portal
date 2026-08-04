<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="포털 운영 설정" :crumbs="['HPC Portal Admin', '운영']" sub="공지·템플릿·세션 정책·감사 로그" />

  <div class="space-y-5">
    <Card title="세션 · 알림 정책" flush>
      <template #title-extra><Fid id="A-OP-04" /></template>
      <NotImplemented api="GET /settings" />
    </Card>
    <Card title="공지 / 템플릿" flush>
      <template #title-extra><Fid id="A-OP-01" /></template>
      <NotImplemented api="GET /notices, /templates" />
    </Card>
    <Card title="감사 로그" flush>
      <template #title-extra><Fid id="A-OP-03" /></template>
      <NotImplemented api="GET /audit-logs" />
    </Card>
  </div>
</template>
