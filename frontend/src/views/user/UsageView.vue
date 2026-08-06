<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { accountApi, type MyFairshare, type MyUsage } from '@/api/account'
import { useClusterStore } from '@/stores/cluster'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-09 내 사용량 / 프로필 (U-AC-01·02·03). 전부 본인 것만 조회된다. */
const clusters = useClusterStore()
const days = ref(30)
const usage = ref<MyUsage | null>(null)
const fairshare = ref<MyFairshare | null>(null)
const loading = ref(false)
const errors = ref<{ usage: unknown; fairshare: unknown }>({ usage: null, fairshare: null })

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [u, f] = await Promise.allSettled([
    accountApi.usage(cid, days.value),
    accountApi.fairshare(cid),
  ])
  usage.value = u.status === 'fulfilled' ? u.value : null
  fairshare.value = f.status === 'fulfilled' ? f.value : null
  errors.value = {
    usage: u.status === 'rejected' ? u.reason : null,
    fairshare: f.status === 'rejected' ? f.reason : null,
  }
  loading.value = false
}
onMounted(load)
watch(() => clusters.selectedId, load)

/** 막대 길이는 최댓값 기준 상대치 — 절대값은 옆에 숫자로 읽는다(Billing과 같은 방식). */
const peak = computed(() => Math.max(1, ...(usage.value?.daily ?? []).map((d) => d.cpu_hours)))
/** 한도가 없으면 null로 온다. 0으로 표시하면 "0개 제한"으로 오해된다. */
const limit = (v: number | null, unit = '') => (v === null ? '무제한' : `${v}${unit}`)
const fixed = (v: number | null, digits = 3) => (v === null ? '—' : v.toFixed(digits))

const inputClass =
  'w-full px-3 py-2 border border-line rounded-lg text-[14.5px] outline-none focus:border-brand-500'
</script>

<template>
  <PageHead
    title="내 사용량 / 프로필"
    :crumbs="['HPC Portal', '내 정보']"
    :sub="`기간별 CPU/GPU 시간과 계정 정보 · ${clusters.selectedName}`"
  >
    <template #actions>
      <select v-model.number="days" :class="[inputClass, 'w-auto']" @change="load">
        <option :value="7">최근 7일</option>
        <option :value="30">최근 30일</option>
        <option :value="90">최근 90일</option>
      </select>
      <Btn @click="load">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="사용량 통계" flush>
      <template #title-extra><Fid id="U-AC-01" /></template>
      <ErrorNote :error="errors.usage" class="m-4" />
      <Empty v-if="!usage && !errors.usage" text="사용량 데이터가 없습니다." />
      <template v-else-if="usage">
        <div class="px-4 py-3 border-b border-line flex flex-wrap items-center gap-5">
          <span class="text-[13px] text-ink-3">{{ usage.start }} ~ {{ usage.end }}</span>
          <div><span class="text-[13px] text-ink-3">Job </span><b class="mono text-[19px]">{{ usage.total_jobs }}</b></div>
          <div><span class="text-[13px] text-ink-3">CPU 시간 </span><b class="mono text-[19px]">{{ usage.total_cpu_hours }}</b></div>
          <div><span class="text-[13px] text-ink-3">GPU 시간 </span><b class="mono text-[19px]">{{ usage.total_gpu_hours }}</b></div>
          <Chip :tone="usage.failed_jobs ? 'violet' : 'gray'">실패 {{ usage.failed_jobs }}</Chip>
        </div>

        <Empty v-if="!usage.daily.length" text="이 기간에 실행한 Job이 없습니다." />
        <div v-else class="p-4 space-y-1.5">
          <div v-for="d in usage.daily" :key="d.date" class="flex items-center gap-3">
            <span class="w-24 shrink-0 mono text-[13px] text-ink-3">{{ d.date }}</span>
            <div class="flex-1 h-3 rounded bg-idle-bg overflow-hidden">
              <div class="h-full rounded bg-brand-700" :style="{ width: (d.cpu_hours / peak) * 100 + '%' }" />
            </div>
            <span class="w-32 shrink-0 mono text-[13px] text-right">{{ d.cpu_hours }} CPU·h</span>
            <span class="w-16 shrink-0 mono text-[13px] text-right text-ink-3">{{ d.jobs }}건</span>
          </div>
        </div>

        <div class="grid sm:grid-cols-2 gap-5 p-4 border-t border-line">
          <div
            v-for="g in [
              { title: '파티션별', rows: usage.by_partition },
              { title: '계정별', rows: usage.by_account },
            ]"
            :key="g.title"
          >
            <p class="text-[13px] font-bold text-ink-3 mb-2">{{ g.title }}</p>
            <div v-for="r in g.rows" :key="r.label" class="flex justify-between text-[14px] py-1">
              <span class="mono">{{ r.label }}</span>
              <b class="mono">{{ r.cpu_hours }} CPU·h <span class="text-ink-3">/ {{ r.jobs }}건</span></b>
            </div>
          </div>
        </div>
      </template>
    </Card>

    <Card title="Fairshare / QOS 한도" flush>
      <template #title-extra><Fid id="U-AC-02" /></template>
      <ErrorNote :error="errors.fairshare" class="m-4" />
      <template v-if="fairshare">
        <div class="p-4 border-b border-line">
          <p class="text-[13px] font-bold text-ink-3 mb-2">소속 계정</p>
          <Empty v-if="!fairshare.associations.length" text="속한 계정이 없습니다." />
          <div
            v-for="a in fairshare.associations"
            :key="`${a.account}-${a.partition}`"
            class="flex flex-wrap items-center gap-2 py-1.5 text-[14.5px]"
          >
            <b class="mono">{{ a.account }}</b>
            <Chip v-if="a.is_default" tone="brand">기본</Chip>
            <span class="text-[13px] text-ink-3">shares {{ a.shares_raw ?? '—' }}</span>
            <Chip v-for="q in a.qos" :key="q" tone="gray">{{ q }}</Chip>
          </div>
        </div>

        <div class="p-4 border-b border-line">
          <p class="text-[13px] font-bold text-ink-3 mb-2">Fairshare</p>
          <!-- slurmrestd에는 계산된 fairshare가 없어 sshare(SSH)로 받는다 -->
          <Empty v-if="!fairshare.shares.length" text="클러스터가 fairshare 값을 제공하지 않습니다." />
          <Table
            v-else
            :columns="[
              { key: 'acct', label: '계정' },
              { key: 'norm', label: '정규 shares' },
              { key: 'use', label: '실효 사용률' },
              { key: 'fs', label: 'FairShare' },
            ]"
          >
            <tr v-for="s in fairshare.shares" :key="`${s.account}-${s.user}`" class="border-b border-line last:border-0">
              <td class="px-3.5 py-2.5 mono">{{ s.account }}</td>
              <td class="px-3.5 py-2.5 mono">{{ fixed(s.norm_shares) }}</td>
              <td class="px-3.5 py-2.5 mono">{{ fixed(s.effective_usage) }}</td>
              <td class="px-3.5 py-2.5 mono">{{ fixed(s.fairshare) }}</td>
            </tr>
          </Table>
        </div>

        <div class="p-4">
          <p class="text-[13px] font-bold text-ink-3 mb-2">QOS 한도</p>
          <Empty v-if="!fairshare.qos.length" text="적용된 QOS가 없습니다." />
          <Table
            v-else
            :columns="[
              { key: 'name', label: 'QOS' },
              { key: 'prio', label: '우선순위' },
              { key: 'wall', label: '최대 실행 시간' },
              { key: 'jobs', label: '동시 Job' },
              { key: 'sub', label: '제출 한도' },
            ]"
          >
            <tr v-for="q in fairshare.qos" :key="q.name" class="border-b border-line last:border-0">
              <td class="px-3.5 py-2.5 mono">
                {{ q.name }}
                <span v-if="q.description" class="text-[13px] text-ink-3"> · {{ q.description }}</span>
              </td>
              <td class="px-3.5 py-2.5 mono">{{ q.priority ?? '—' }}</td>
              <td class="px-3.5 py-2.5 mono">{{ limit(q.max_wall_minutes, '분') }}</td>
              <td class="px-3.5 py-2.5 mono">{{ limit(q.max_jobs_per_user, '개') }}</td>
              <td class="px-3.5 py-2.5 mono">{{ limit(q.max_submit_per_user, '개') }}</td>
            </tr>
          </Table>
        </div>
      </template>
    </Card>

  </div>
</template>
