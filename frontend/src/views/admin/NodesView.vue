<script setup lang="ts">
import { ref, watch } from 'vue'
import { clusterApi, type ReservationCreate } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import { mib, num, numText, resourceTone, states, text, type SlurmRecord } from '@/utils/slurm'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import Fid from '@/components/ui/Fid.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/**
 * SCR-11 — 노드·파티션·예약을 slurmrestd에서 조회하고(A-ND-02·03·04),
 * 노드 상태를 제어한다(A-ND-01). 파티션·예약 쓰기는 아직 없다.
 */
const clusters = useClusterStore()
const nodes = ref<SlurmRecord[]>([])
const partitions = ref<SlurmRecord[]>([])
const reservations = ref<SlurmRecord[]>([])
const loading = ref(false)
/**
 * 오류는 패널별로 따로 잡는다.
 * 세 조회는 서로 독립인데 하나로 묶으면(Promise.all) 한쪽 실패가 나머지 성공분까지 버린다.
 * 실제로 slurmdbd가 끊기면 slurmrestd가 파티션 조회에만 500을 돌려주는 상황이 있다.
 */
const errors = ref<Record<'nodes' | 'partitions' | 'reservations', unknown>>({
  nodes: null,
  partitions: null,
  reservations: null,
})

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [n, p, r] = await Promise.allSettled([
    clusterApi.nodes(cid),
    clusterApi.partitions(cid),
    clusterApi.reservations(cid),
  ])
  nodes.value = n.status === 'fulfilled' ? n.value : []
  partitions.value = p.status === 'fulfilled' ? p.value : []
  reservations.value = r.status === 'fulfilled' ? r.value : []
  errors.value = {
    nodes: n.status === 'rejected' ? n.reason : null,
    partitions: p.status === 'rejected' ? p.reason : null,
    reservations: r.status === 'rejected' ? r.reason : null,
  }
  loading.value = false
}
watch(() => clusters.selectedId, load, { immediate: true })

/* --- 노드 상태 제어 (A-ND-01) --- */
type NodeAction = 'drain' | 'resume' | 'down'
const dialog = ref<{ node: string; action: NodeAction; reason: string } | null>(null)
const busy = ref(false)

/** 이미 빠져 있나. DRAIN·DRAINED·DOWN 중 하나면 되돌리기만 의미가 있다. */
function isDrained(n: SlurmRecord): boolean {
  return states(n).some((s) => s.startsWith('DRAIN') || s === 'DOWN')
}

const ACTION_LABEL: Record<NodeAction, string> = {
  drain: '노드 빼기 (drain)',
  resume: '노드 되돌리기 (resume)',
  down: '노드 down 처리',
}

function ask(n: SlurmRecord, action: NodeAction) {
  dialog.value = { node: String(n.name), action, reason: '' }
  errors.value.nodes = null
}

async function applyState() {
  const d = dialog.value
  const cid = clusters.selectedId
  if (!d || !cid) return
  busy.value = true
  try {
    await clusterApi.setNodeState(cid, d.node, d.action, d.reason.trim() || undefined)
    dialog.value = null
    await load()
  } catch (e) {
    errors.value.nodes = e
  } finally {
    busy.value = false
  }
}

const resInput =
  'w-full px-3 py-2 rounded-lg border border-line-dark text-[14.5px] outline-none focus:border-brand-500'

/* --- 예약 (A-ND-04) --- */
const showReservation = ref(false)
/**
 * 폼은 **로컬 시각**을 받고 epoch으로 바꿔 보낸다. slurmrestd는 epoch만 받고,
 * 관리자는 "8월 9일 22시"로 생각한다 — 변환은 화면이 한다.
 */
const resForm = ref({
  name: '', start_local: '', duration_minutes: 120,
  node_list: '', node_count: null as number | null,
  users: '', accounts: '', maint: true, ignore_jobs: false, comment: '',
})

function openReservation() {
  const now = new Date(Date.now() + 60 * 60 * 1000)
  now.setSeconds(0, 0)
  // datetime-local은 UTC가 아니라 로컬 문자열을 요구한다 — 오프셋을 빼고 잘라 준다.
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  resForm.value = {
    name: '', start_local: local.toISOString().slice(0, 16), duration_minutes: 120,
    node_list: '', node_count: null, users: '', accounts: '',
    maint: true, ignore_jobs: false, comment: '',
  }
  errors.value.reservations = null
  showReservation.value = true
}

async function createReservation() {
  const cid = clusters.selectedId
  const f = resForm.value
  if (!cid || !f.start_local) return
  const flags = [...(f.maint ? ['MAINT'] : []), ...(f.ignore_jobs ? ['IGNORE_JOBS'] : [])]
  const body: ReservationCreate = {
    name: f.name.trim(),
    start_time: Math.floor(new Date(f.start_local).getTime() / 1000),
    duration_minutes: f.duration_minutes,
    node_list: f.node_list.trim() || null,
    node_count: f.node_count,
    users: f.users.trim() || null,
    accounts: f.accounts.trim() || null,
    comment: f.comment.trim() || null,
    flags,
  }
  busy.value = true
  try {
    await clusterApi.createReservation(cid, body)
    showReservation.value = false
    await load()
  } catch (e) {
    errors.value.reservations = e
  } finally {
    busy.value = false
  }
}

async function removeReservation(name: string) {
  const cid = clusters.selectedId
  if (!cid) return
  if (!confirm(`예약 '${name}' 을(를) 삭제할까요?`)) return
  try {
    await clusterApi.deleteReservation(cid, name)
    await load()
  } catch (e) {
    errors.value.reservations = e
  }
}

function cpuText(n: SlurmRecord): string {
  const total = num(n.cpus)
  return total === null ? '—' : `${num(n.alloc_cpus) ?? 0} / ${total}`
}

function memText(n: SlurmRecord): string {
  return num(n.real_memory) === null ? '—' : `${mib(n.alloc_memory)} / ${mib(n.real_memory)}`
}

const sub = (row: SlurmRecord, key: string): SlurmRecord =>
  (row[key] as SlurmRecord | undefined) ?? {}
</script>

<template>
  <PageHead
    title="노드 / 파티션 관리"
    :crumbs="['HPC Portal Admin', '자원 관리']"
    :sub="`노드 상태와 파티션 구성 · ${clusters.selectedName}`"
  >
    <template #actions><Btn @click="load">↻ 새로고침</Btn></template>
  </PageHead>

  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="노드" flush>
      <template #title-extra><Fid id="A-ND-02" /></template>
      <ErrorNote :error="errors.nodes" class="m-4" />
      <Empty v-if="!nodes.length && !errors.nodes" text="노드가 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '노드' },
          { key: 'state', label: '상태' },
          { key: 'part', label: '파티션' },
          { key: 'cpu', label: 'CPU (할당/전체)', num: true },
          { key: 'mem', label: '메모리 (할당/전체)', num: true },
          { key: 'load', label: 'CPU Load', num: true },
          { key: 'gres', label: 'GRES' },
          { key: 'reason', label: '사유' },
          { key: 'act', label: '액션', width: '150px' },
        ]"
      >
        <tr v-for="n in nodes" :key="String(n.name)" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(n, 'name') }}</td>
          <td class="px-3.5 py-2.5">
            <span class="flex flex-wrap gap-1">
              <Badge v-for="s in states(n)" :key="s" :state="resourceTone(s)">{{ s }}</Badge>
            </span>
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(n, 'partitions') }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ cpuText(n) }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ memText(n) }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(n.cpu_load) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(n, 'gres') }}</td>
          <td class="px-3.5 py-2.5 text-[13px] text-ink-3">{{ text(n, 'reason') }}</td>
          <td class="px-3.5 py-2.5">
            <!-- 이미 빠져 있는 노드에 '빼기'를, 살아 있는 노드에 '되돌리기'를 보여주지
                 않는다 — 누를 수 있는데 아무 일도 안 나는 버튼이 된다 -->
            <div class="flex gap-1.5">
              <Btn v-if="isDrained(n)" size="sm" @click="ask(n, 'resume')">되돌리기</Btn>
              <template v-else>
                <Btn size="sm" @click="ask(n, 'drain')">빼기</Btn>
                <Btn size="sm" variant="danger" @click="ask(n, 'down')">down</Btn>
              </template>
            </div>
          </td>
        </tr>
      </Table>
    </Card>

    <Card title="파티션" flush>
      <template #title-extra><Fid id="A-ND-03" /></template>
      <ErrorNote :error="errors.partitions" class="m-4" />
      <Empty v-if="!partitions.length && !errors.partitions" text="파티션이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '파티션' },
          { key: 'state', label: '상태' },
          { key: 'nodes', label: '노드' },
          { key: 'cnt', label: '노드 수', num: true },
          { key: 'cpus', label: 'CPU', num: true },
          { key: 'time', label: '최대 실행시간', num: true },
          { key: 'prio', label: '우선순위', num: true },
        ]"
      >
        <tr v-for="p in partitions" :key="String(p.name)" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(p, 'name') }}</td>
          <td class="px-3.5 py-2.5">
            <Badge v-for="s in states(sub(p, 'partition'))" :key="s" :state="resourceTone(s)">
              {{ s }}
            </Badge>
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(sub(p, 'nodes'), 'configured') }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'nodes').total) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'cpus').total) ?? '—' }}</td>
          <td class="px-3.5 py-2.5 mono text-right">
            {{ numText(sub(p, 'maximums').time, '분') }}
          </td>
          <td class="px-3.5 py-2.5 mono text-right">{{ num(sub(p, 'priority').tier) ?? '—' }}</td>
        </tr>
      </Table>
    </Card>

    <Card title="예약" flush>
      <template #title-extra><Fid id="A-ND-04" /></template>
      <template #head><Btn size="sm" @click="openReservation">＋ 예약 생성</Btn></template>
      <ErrorNote :error="errors.reservations" class="m-4" />
      <Empty v-if="!reservations.length && !errors.reservations" text="예약이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '예약명' },
          { key: 'nodes', label: '노드' },
          { key: 'users', label: '사용자' },
          { key: 'accounts', label: '계정' },
          { key: 'start', label: '시작', num: true },
          { key: 'end', label: '종료', num: true },
          { key: 'act', label: '액션', width: '90px' },
        ]"
      >
        <tr
          v-for="r in reservations"
          :key="String(r.name)"
          class="border-b border-line last:border-0"
        >
          <td class="px-3.5 py-2.5 mono font-semibold">{{ text(r, 'name') }}</td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ text(r, 'node_list') }}</td>
          <td class="px-3.5 py-2.5 text-[13px]">{{ text(r, 'users') }}</td>
          <td class="px-3.5 py-2.5 text-[13px]">{{ text(r, 'accounts') }}</td>
          <td class="px-3.5 py-2.5 mono text-right text-[13px]">{{ numText(r.start_time) }}</td>
          <td class="px-3.5 py-2.5 mono text-right text-[13px]">{{ numText(r.end_time) }}</td>
          <td class="px-3.5 py-2.5">
            <Btn size="sm" variant="danger" @click="removeReservation(String(r.name))">삭제</Btn>
          </td>
        </tr>
      </Table>
    </Card>
  </div>

  <Modal
    v-if="dialog"
    :title="ACTION_LABEL[dialog.action]"
    @close="dialog = null"
  >
    <template #title-extra><Fid id="A-ND-01" /></template>
    <p class="text-[14px] text-ink-3 mb-4">
      <b class="mono text-ink">{{ dialog.node }}</b>
      <template v-if="dialog.action === 'drain'">
        — 실행 중인 Job은 끝까지 돌고, <b>새 Job만 배정되지 않습니다.</b>
      </template>
      <template v-else-if="dialog.action === 'down'">
        — <b class="text-err">실행 중인 Job이 즉시 종료됩니다.</b> 하드웨어 장애처럼
        노드를 당장 쓸 수 없을 때만 쓰세요.
      </template>
      <template v-else>— 다시 스케줄링 대상이 됩니다.</template>
    </p>
    <!-- 사유는 Slurm이 노드에 붙여 둔다. 나중에 "왜 빠져 있지?"에 답하는 단서다. -->
    <label v-if="dialog.action !== 'resume'" class="block text-[13px] text-ink-3">
      사유 (필수)
      <input
        v-model="dialog.reason" class="w-full mt-1 px-3 py-2 rounded-lg border border-line-dark
        text-[14.5px] outline-none focus:border-brand-500" placeholder="예: 디스크 교체"
        @keyup.enter="applyState"
      />
    </label>
    <template #foot>
      <Btn @click="dialog = null">취소</Btn>
      <Btn
        :variant="dialog.action === 'down' ? 'danger' : 'primary'"
        :disabled="busy || (dialog.action !== 'resume' && !dialog.reason.trim())"
        @click="applyState"
      >{{ busy ? '적용 중…' : '적용' }}</Btn>
    </template>
  </Modal>

  <Modal v-if="showReservation" title="예약 생성" wide @close="showReservation = false">
    <template #title-extra><Fid id="A-ND-04" /></template>
    <ErrorNote :error="errors.reservations" class="mb-4" />
    <div class="grid sm:grid-cols-2 gap-4">
      <Field label="예약명" required hint="영문·숫자·. _ - 만">
        <input v-model="resForm.name" :class="[resInput, 'mono']" placeholder="maint-2026-08-09" />
      </Field>
      <Field label="시작 시각" required hint="브라우저 로컬 시각 — 서버가 epoch으로 변환합니다">
        <input v-model="resForm.start_local" type="datetime-local" :class="resInput" />
      </Field>
      <Field label="기간 (분)" required hint="종료 시각 대신 기간으로 받습니다">
        <input v-model.number="resForm.duration_minutes" type="number" min="1" :class="[resInput, 'mono']" />
      </Field>
      <!-- 둘 중 하나는 필수다. 없으면 Slurm이 클러스터 전체를 잡을 수 있어 서버가 막는다 -->
      <Field label="노드 수" hint="노드 목록을 비울 때 사용">
        <input v-model.number="resForm.node_count" type="number" min="1" :class="[resInput, 'mono']" />
      </Field>
      <Field label="노드 목록" full hint="예: slurm[01-02] — 노드 수보다 우선합니다">
        <input v-model="resForm.node_list" :class="[resInput, 'mono']" placeholder="slurm[01-02]" />
      </Field>
      <Field label="사용자" hint="쉼표 구분 — 사용자나 계정 중 하나는 필수(Slurm 요구)">
        <input v-model="resForm.users" :class="[resInput, 'mono']" />
      </Field>
      <Field label="계정" hint="쉼표 구분 — 사용자를 비웠다면 여기를 채웁니다">
        <input v-model="resForm.accounts" :class="[resInput, 'mono']" />
      </Field>
      <Field label="설명" full><input v-model="resForm.comment" :class="resInput" /></Field>
      <div class="sm:col-span-2 flex flex-wrap gap-5">
        <label class="flex items-center gap-2 text-[14.5px]">
          <input v-model="resForm.maint" type="checkbox" class="w-4 h-4 accent-brand-700" />
          점검 (MAINT) — 예약 구간에 다른 Job을 배정하지 않습니다
        </label>
        <label class="flex items-center gap-2 text-[14.5px]">
          <input v-model="resForm.ignore_jobs" type="checkbox" class="w-4 h-4 accent-brand-700" />
          실행 중 Job 무시 (IGNORE_JOBS)
        </label>
      </div>
    </div>
    <template #foot>
      <Btn @click="showReservation = false">취소</Btn>
      <Btn
        variant="primary"
        :disabled="busy || !resForm.name.trim() || !resForm.start_local
          || (!resForm.node_list.trim() && !resForm.node_count)
          || (!resForm.users.trim() && !resForm.accounts.trim())"
        @click="createReservation"
      >{{ busy ? '생성 중…' : '생성' }}</Btn>
    </template>
  </Modal>

</template>
