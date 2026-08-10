<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { opsApi, type AuditLog } from '@/api/ops'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'
import { inputBase } from '@/utils/form'

/**
 * SCR-23 감사 로그 (A-OP-03, C-05) — 포탈 설정 콘솔.
 *
 * 포털 내 **제어성 행위**(제출·취소·설정 변경·계정 관리·로그인)가 기록된다.
 * 읽기 전용이다 — 지우거나 고치는 길은 화면에도 API에도 없다.
 *
 * 추적 범위는 **포털의 행적**이다. 포털 밖에서 일어난 일은 애초에 이 화면의 대상이 아니다.
 */
const logs = ref<AuditLog[]>([])
const logTotal = ref(0)
const actions = ref<string[]>([])
const error = ref<unknown>(null)
const loading = ref(false)

const filter = ref({ action: '', actor_username: '', page: 1, size: 25 })

async function loadLogs() {
  loading.value = true
  try {
    const page = await opsApi.auditLogs(filter.value)
    logs.value = page.items
    logTotal.value = page.total
    error.value = null
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 액션 목록은 필터 드롭다운용이라 한 번만 받는다. 실패해도 목록은 보여야 한다.
  actions.value = await opsApi.auditActions().catch(() => [])
  await loadLogs()
})

const pages = computed(() => Math.max(1, Math.ceil(logTotal.value / filter.value.size)))

function goPage(delta: number) {
  const next = filter.value.page + delta
  if (next < 1 || next > pages.value) return
  filter.value.page = next
  loadLogs()
}

function applyFilter() {
  filter.value.page = 1
  loadLogs()
}

function reset() {
  filter.value = { action: '', actor_username: '', page: 1, size: 25 }
  loadLogs()
}

</script>

<template>
  <PageHead
    title="감사 로그"
    :crumbs="['HPC Portal Admin', '운영', '감사 로그']"
    sub="포털 내 제어성 행위 기록 (C-05)"
  >
    <template #actions>
      <Btn @click="loadLogs">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <Card title="기록" flush>
    <template #title-extra><Fid id="A-OP-03" /></template>

    <div class="p-4 border-b border-line flex flex-wrap gap-3 items-end">
      <label class="text-[13px] text-ink-3">
        액션
        <select v-model="filter.action" :class="[inputBase, 'w-[220px] mt-1 block']" @change="applyFilter">
          <option value="">전체</option>
          <option v-for="a in actions" :key="a" :value="a">{{ a }}</option>
        </select>
      </label>
      <label class="text-[13px] text-ink-3">
        행위자 (계정명)
        <input
          v-model="filter.actor_username" :class="[inputBase, 'w-[260px] mono mt-1 block']"
          placeholder="jungryul0515.park" @keyup.enter="applyFilter"
        />
      </label>
      <Btn @click="applyFilter">조회</Btn>
      <!-- 필터를 걸어 둔 채 잊는 일이 잦다 — 되돌릴 길을 옆에 둔다 -->
      <Btn v-if="filter.action || filter.actor_username" @click="reset">초기화</Btn>

      <span class="ml-auto text-[13px] text-ink-3">
        총 {{ logTotal }}건 · {{ filter.page }} / {{ pages }} 페이지
      </span>
      <Btn size="sm" :disabled="filter.page <= 1" @click="goPage(-1)">이전</Btn>
      <Btn size="sm" :disabled="filter.page >= pages" @click="goPage(1)">다음</Btn>
    </div>

    <Empty
      v-if="!logs.length"
      :text="loading ? '불러오는 중…' : '조건에 맞는 감사 로그가 없습니다.'"
    />
    <Table
      v-else
      :columns="[
        { key: 'at', label: '시각' },
        { key: 'actor', label: '행위자' },
        { key: 'action', label: '액션' },
        { key: 'target', label: '대상' },
        { key: 'detail', label: '상세' },
      ]"
    >
      <tr v-for="l in logs" :key="l.id" class="border-b border-line last:border-0">
        <td class="px-3.5 py-2.5 mono text-[13px] whitespace-nowrap">
          {{ new Date(l.at).toLocaleString('ko-KR') }}
        </td>
        <td class="px-3.5 py-2.5">
          {{ l.actor ?? '—' }}
          <Chip v-if="l.actor_role" tone="gray">{{ l.actor_role }}</Chip>
        </td>
        <td class="px-3.5 py-2.5 mono text-[13px]">{{ l.action }}</td>
        <td class="px-3.5 py-2.5 mono text-[13px] truncate max-w-[220px]">{{ l.target ?? '—' }}</td>
        <td class="px-3.5 py-2.5 text-[13px] text-ink-3 truncate max-w-[320px]">
          {{ l.detail ?? '—' }}
        </td>
      </tr>
    </Table>

    <template #foot>
      포털 내 제어성 행위(제출·취소·설정 변경·계정 관리)가 기록됩니다 (C-05).
    </template>
  </Card>
</template>
