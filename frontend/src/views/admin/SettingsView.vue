<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  opsApi,
  type AuditLog,
  type Notice,
  type Settings,
} from '@/api/ops'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-15 포털 운영 설정 (A-OP-01·03·04). 전부 Portal DB 소유 — 클러스터 호출이 없다. */
const settings = ref<Settings | null>(null)
const notices = ref<Notice[]>([])
const logs = ref<AuditLog[]>([])
const logTotal = ref(0)
const actions = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const errors = ref<Record<string, unknown>>({})

const filter = ref({ action: '', actor_username: '', page: 1, size: 25 })
const noticeForm = ref({ title: '', body: '', banner_enabled: false })

async function load() {
  loading.value = true
  const [s, n, a] = await Promise.allSettled([
    opsApi.settings(),
    opsApi.notices(),
    opsApi.auditActions(),
  ])
  settings.value = s.status === 'fulfilled' ? s.value : null
  notices.value = n.status === 'fulfilled' ? n.value : []
  actions.value = a.status === 'fulfilled' ? a.value : []
  errors.value = {
    settings: s.status === 'rejected' ? s.reason : null,
    notices: n.status === 'rejected' ? n.reason : null,
  }
  await loadLogs()
  loading.value = false
}

async function loadLogs() {
  try {
    const page = await opsApi.auditLogs(filter.value)
    logs.value = page.items
    logTotal.value = page.total
    errors.value = { ...errors.value, logs: null }
  } catch (e) {
    errors.value = { ...errors.value, logs: e }
  }
}

async function saveSettings() {
  if (!settings.value) return
  saving.value = true
  errors.value = { ...errors.value, settings: null }
  try {
    settings.value = await opsApi.updateSettings({
      poll_interval_sec: settings.value.poll_interval_sec,
      session_timeout_min: settings.value.session_timeout_min,
      smtp_host: settings.value.smtp_host,
      smtp_port: settings.value.smtp_port,
      smtp_sender: settings.value.smtp_sender,
      webhook_url: settings.value.webhook_url,
    })
    await loadLogs()
  } catch (e) {
    errors.value = { ...errors.value, settings: e }
  } finally {
    saving.value = false
  }
}

async function addNotice() {
  if (!noticeForm.value.title.trim()) return
  try {
    await opsApi.createNotice({ ...noticeForm.value })
    noticeForm.value = { title: '', body: '', banner_enabled: false }
    notices.value = await opsApi.notices()
    await loadLogs()
  } catch (e) {
    errors.value = { ...errors.value, notices: e }
  }
}

async function toggleBanner(n: Notice) {
  await opsApi.updateNotice(n.id, { banner_enabled: !n.banner_enabled })
  notices.value = await opsApi.notices()
}

async function removeNotice(id: number) {
  await opsApi.removeNotice(id)
  notices.value = await opsApi.notices()
  await loadLogs()
}

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

onMounted(load)

const inputClass =
  'w-full px-3 py-2 border border-line rounded-lg text-[14.5px] outline-none focus:border-brand-500'
</script>

<template>
  <PageHead
    title="포털 운영 설정"
    :crumbs="['HPC Portal Admin', '운영']"
    sub="공지·앱·세션 정책·감사 로그"
  >
    <template #actions><Btn @click="load">↻ 새로고침</Btn></template>
  </PageHead>

  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="세션 · 알림 정책">
      <template #title-extra><Fid id="A-OP-04" /></template>
      <ErrorNote :error="errors.settings" />
      <div v-if="settings" class="grid sm:grid-cols-3 gap-4">
        <label class="text-[13px] text-ink-3">
          폴링 주기 (초)
          <input
            v-model.number="settings.poll_interval_sec" type="number" min="5" max="30"
            :class="[inputClass, 'mono mt-1']"
          />
          <span class="block mt-1 text-[12.5px]">C-04 — 5~30초</span>
        </label>
        <label class="text-[13px] text-ink-3">
          세션 타임아웃 (분)
          <input
            v-model.number="settings.session_timeout_min" type="number" min="5"
            :class="[inputClass, 'mono mt-1']"
          />
        </label>
        <div class="text-[13px] text-ink-3 flex items-end">
          <span>
            마지막 수정
            <b class="mono block text-ink-2">
              {{ settings.updated_at ? new Date(settings.updated_at).toLocaleString('ko-KR') : '—' }}
            </b>
          </span>
        </div>

        <label class="text-[13px] text-ink-3">
          SMTP 호스트
          <input v-model="settings.smtp_host" :class="[inputClass, 'mono mt-1']" placeholder="smtp.dt-hpc.net" />
        </label>
        <label class="text-[13px] text-ink-3">
          SMTP 포트
          <input v-model.number="settings.smtp_port" type="number" :class="[inputClass, 'mono mt-1']" placeholder="587" />
        </label>
        <label class="text-[13px] text-ink-3">
          발신 주소
          <input v-model="settings.smtp_sender" :class="[inputClass, 'mono mt-1']" placeholder="hpc-portal@dt-hpc.net" />
        </label>
        <label class="sm:col-span-3 text-[13px] text-ink-3">
          웹훅 URL
          <input v-model="settings.webhook_url" :class="[inputClass, 'mono mt-1']" placeholder="https://hooks.…" />
        </label>
        <div class="sm:col-span-3 flex items-center gap-3">
          <Btn variant="primary" :disabled="saving" @click="saveSettings">
            {{ saving ? '저장 중…' : '설정 저장' }}
          </Btn>
          <span class="text-[13px] text-ink-3">
            변경하면 감사 로그에 <b>바뀐 항목 이름만</b> 기록됩니다 — 값은 남기지 않습니다.
          </span>
        </div>
      </div>
    </Card>

    <Card title="공지" flush>
      <template #title-extra><Fid id="A-OP-01" /></template>
      <ErrorNote :error="errors.notices" class="m-4" />
      <div class="p-4 border-b border-line grid sm:grid-cols-[1fr_2fr_auto_auto] gap-3 items-end">
        <label class="text-[13px] text-ink-3">
          제목
          <input v-model="noticeForm.title" :class="[inputClass, 'mt-1']" placeholder="정기 점검 안내" />
        </label>
        <label class="text-[13px] text-ink-3">
          내용
          <input v-model="noticeForm.body" :class="[inputClass, 'mt-1']" />
        </label>
        <label class="flex items-center gap-2 text-[13.5px] text-ink-2 pb-2">
          <input v-model="noticeForm.banner_enabled" type="checkbox" /> 배너 노출
        </label>
        <Btn variant="primary" @click="addNotice">등록</Btn>
      </div>
      <Empty v-if="!notices.length" text="등록된 공지가 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'title', label: '제목' },
          { key: 'body', label: '내용' },
          { key: 'banner', label: '배너' },
          { key: 'at', label: '등록일' },
          { key: 'act', label: '', width: '150px' },
        ]"
      >
        <tr v-for="n in notices" :key="n.id" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5"><b>{{ n.title }}</b></td>
          <td class="px-3.5 py-2.5 text-ink-3 truncate max-w-[420px]">{{ n.body ?? '—' }}</td>
          <td class="px-3.5 py-2.5">
            <Badge :state="n.banner_enabled ? 'idle' : 'down'">
              {{ n.banner_enabled ? '노출' : '숨김' }}
            </Badge>
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]">
            {{ new Date(n.created_at).toLocaleDateString('ko-KR') }}
          </td>
          <td class="px-3.5 py-2.5 flex gap-2">
            <Btn size="sm" @click="toggleBanner(n)">{{ n.banner_enabled ? '숨김' : '노출' }}</Btn>
            <Btn size="sm" variant="danger" @click="removeNotice(n.id)">삭제</Btn>
          </td>
        </tr>
      </Table>
    </Card>

    <Card title="감사 로그" flush>
      <template #title-extra><Fid id="A-OP-03" /></template>
      <ErrorNote :error="errors.logs" class="m-4" />
      <div class="p-4 border-b border-line flex flex-wrap gap-3 items-end">
        <label class="text-[13px] text-ink-3">
          액션
          <select v-model="filter.action" :class="[inputClass, 'w-auto mt-1']" @change="applyFilter">
            <option value="">전체</option>
            <option v-for="a in actions" :key="a" :value="a">{{ a }}</option>
          </select>
        </label>
        <label class="text-[13px] text-ink-3">
          행위자 (계정명)
          <input
            v-model="filter.actor_username" :class="[inputClass, 'w-auto mono mt-1']"
            placeholder="jungryul0515.park" @keyup.enter="applyFilter"
          />
        </label>
        <Btn @click="applyFilter">조회</Btn>
        <span class="ml-auto text-[13px] text-ink-3">
          총 {{ logTotal }}건 · {{ filter.page }} / {{ pages }} 페이지
        </span>
        <Btn size="sm" :disabled="filter.page <= 1" @click="goPage(-1)">이전</Btn>
        <Btn size="sm" :disabled="filter.page >= pages" @click="goPage(1)">다음</Btn>
      </div>
      <Empty v-if="!logs.length" text="조건에 맞는 감사 로그가 없습니다." />
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
  </div>
</template>
