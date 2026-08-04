<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="공지사항" :crumbs="['HPC Portal', '공지사항']" sub="관리자가 등록한 점검·정책 공지" />

  <div class="space-y-5">
    <Card title="공지 목록" flush>
      <template #title-extra><Fid id="U-CL-03" /></template>
      <NotImplemented api="GET /notices" />
    </Card>
  </div>
</template>
