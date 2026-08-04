<script setup lang="ts">
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import NotImplemented from '@/components/ui/NotImplemented.vue'
import PageHead from '@/components/ui/PageHead.vue'
</script>

<template>
  <PageHead title="내 사용량 / 프로필" :crumbs="['HPC Portal', '내 정보']" sub="기간별 CPU/GPU 시간과 계정 정보" />

  <div class="space-y-5">
    <Card title="사용량 통계" flush>
      <template #title-extra><Fid id="U-AC-01" /></template>
      <NotImplemented api="GET /clusters/{cid}/me/usage" />
    </Card>
    <Card title="Fairshare / QOS 한도" flush>
      <template #title-extra><Fid id="U-AC-02" /></template>
      <NotImplemented api="GET /clusters/{cid}/me/fairshare" />
    </Card>
    <Card title="SSH 공개키" flush>
      <template #title-extra><Fid id="U-AC-03" /></template>
      <NotImplemented api="GET /me/ssh-keys" />
    </Card>
  </div>
</template>
