<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
import { useClusterStore } from '@/stores/cluster'

const clusters = useClusterStore()
</script>

<template>
  <PageHead title="파일 관리자" :crumbs="['HPC Portal', '작업 환경']" :sub="`로그인 노드 경유 SFTP · ${clusters.selectedName}`" />

  <div class="space-y-5">
    <Card title="파일 브라우저" flush>
      <template #title-extra><Fid id="U-FM-01" /></template>
      <NotImplemented api="GET /clusters/{cid}/files" />
    </Card>
    <Card title="스토리지 사용량" flush>
      <template #title-extra><Fid id="A-DB-05" /></template>
      <NotImplemented api="GET /clusters/{cid}/storage" />
    </Card>
  </div>
</template>
