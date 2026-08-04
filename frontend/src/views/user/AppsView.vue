<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="인터랙티브 앱" :crumbs="['HPC Portal', '작업 환경']" sub="Jupyter · 원격 데스크톱 · VS Code 세션" />

  <div class="space-y-5">
    <Card title="앱 런처" flush>
      <template #title-extra><Fid id="U-IA-01" /></template>
      <NotImplemented api="POST /sessions" />
    </Card>
    <Card title="실행 중 세션" flush>
      <template #title-extra><Fid id="U-IA-04" /></template>
      <NotImplemented api="GET /sessions" />
    </Card>
  </div>
</template>
