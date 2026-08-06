<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionApi, type Session } from '@/api/sessions'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/**
 * SCR-06 인터랙티브 앱 (U-IA-01 런처 · U-IA-04 세션 관리).
 *
 * 세션은 **Slurm 배치 Job**이다 — 폼 값이 sbatch 자원으로 들어가고, 컨테이너가 워커
 * 노드에서 뜬 뒤 접속 정보를 남기면 그때부터 붙을 수 있다.
 */
const router = useRouter()
const clusters = useClusterStore()

const sessions = ref<Session[]>([])
const partitions = ref<string[]>([])
const loading = ref(false)
const submitting = ref(false)
const errors = ref<{ list: unknown; submit: unknown }>({ list: null, submit: null })

const form = ref({
  partition: '',
  cpus: 2,
  memory_gb: 3,
  walltime: '02:00:00',
  geometry: '1280x800',
  exclusive: false,
})

/**
 * 앱 목록. 같은 이미지 안에서 `PORTAL_APP`으로 갈린다 — 세션·프록시 계층은 전부 공유한다.
 * Jupyter·VS Code도 기동 스크립트에 분기만 추가하면 된다.
 */
const APPS = [
  { id: 'desktop', name: '원격 데스크톱', desc: 'MATE 데스크톱 (Rocky 9)', fid: 'U-IA-02', ready: true },
  { id: 'paraview', name: 'ParaView', desc: '과학 시각화 5.11 (소프트웨어 렌더링)', fid: 'U-IA-02', ready: true },
  { id: 'jupyter', name: 'JupyterLab', desc: '노트북 세션', fid: 'U-IA-01', ready: false },
  { id: 'code-server', name: 'VS Code Server', desc: '웹 코드 편집', fid: 'U-IA-03', ready: false },
]
const selectedApp = ref('desktop')
const selected = computed(() => APPS.find((a) => a.id === selectedApp.value) ?? APPS[0])

const active = computed(() => sessions.value.filter((s) => !s.terminated_at && s.state !== 'ENDED'))

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [s, o] = await Promise.allSettled([sessionApi.list(cid), jobApi.options(cid)])
  sessions.value = s.status === 'fulfilled' ? s.value : []
  errors.value.list = s.status === 'rejected' ? s.reason : null
  if (o.status === 'fulfilled') {
    partitions.value = o.value.partitions ?? []
    if (!form.value.partition && partitions.value.length) form.value.partition = partitions.value[0]
  }
  loading.value = false
}

async function launch() {
  const cid = clusters.selectedId
  if (!cid) return
  submitting.value = true
  errors.value.submit = null
  try {
    await sessionApi.create(cid, {
      app: selectedApp.value,
      partition: form.value.partition || null,
      cpus: form.value.cpus,
      memory_gb: form.value.memory_gb,
      walltime: form.value.walltime,
      geometry: form.value.geometry,
      exclusive: form.value.exclusive,
    })
    await load()
  } catch (e) {
    errors.value.submit = e
  } finally {
    submitting.value = false
  }
}

async function terminate(s: Session) {
  if (!confirm(`세션 ${s.job_id}을(를) 종료할까요? 실행 중인 작업이 함께 종료됩니다.`)) return
  try {
    await sessionApi.terminate(s.id)
    await load()
  } catch (e) {
    errors.value.list = e
  }
}

function open(s: Session) {
  router.push({ name: 'desktop', params: { sid: s.id } })
}

/** 제출 직후엔 PENDING이라 붙을 수 없다 — RUNNING으로 바뀌는 것을 폴링으로 본다. */
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (active.value.length) load()
  }, 5000)
})
onBeforeUnmount(() => clearInterval(timer))
watch(() => clusters.selectedId, load)

const inputClass =
  'w-full px-3 py-2 border border-line rounded-lg text-[14.5px] outline-none focus:border-brand-500'
</script>

<template>
  <PageHead
    title="인터랙티브 앱"
    :crumbs="['HPC Portal', '작업 환경']"
    :sub="`브라우저에서 여는 GUI 세션 · ${clusters.selectedName}`"
  >
    <template #actions>
      <Btn @click="load">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <div class="space-y-5">
    <Card title="앱 런처" flush>
      <template #title-extra><Fid id="U-IA-01" /></template>
      <ErrorNote :error="errors.submit" class="m-4" />

      <!-- 카드를 눌러 앱을 고른다. 자원 폼과 제출 버튼은 공유한다. -->
      <div class="grid sm:grid-cols-4 gap-3 p-4 border-b border-line">
        <button
          v-for="a in APPS"
          :key="a.id"
          type="button"
          :disabled="!a.ready"
          class="text-left border rounded-lg p-3.5 transition-colors"
          :class="[
            !a.ready
              ? 'border-line opacity-60 cursor-not-allowed'
              : selectedApp === a.id
                ? 'border-brand-700 ring-2 ring-brand-700/25 bg-bg'
                : 'border-line hover:border-brand-500',
          ]"
          @click="selectedApp = a.id"
        >
          <div class="flex items-center gap-2">
            <b class="text-[15px]">{{ a.name }}</b>
            <Fid :id="a.fid" />
          </div>
          <p class="mt-1 text-[13px] text-ink-3">{{ a.desc }}</p>
          <Chip v-if="!a.ready" tone="gray" class="mt-2">준비 중</Chip>
          <Chip v-else-if="selectedApp === a.id" tone="brand" class="mt-2">선택됨</Chip>
        </button>
      </div>

      <!-- 폼 값이 그대로 sbatch 자원이 된다 (Job 제출과 같은 규칙) -->
      <div class="p-4 grid sm:grid-cols-5 gap-3 items-end">
        <label class="text-[13px] text-ink-3">
          파티션
          <select v-model="form.partition" :class="[inputClass, 'mt-1']">
            <option v-for="p in partitions" :key="p" :value="p">{{ p }}</option>
          </select>
        </label>
        <label class="text-[13px] text-ink-3">
          CPU
          <input v-model.number="form.cpus" type="number" min="1" :class="[inputClass, 'mono mt-1']" />
        </label>
        <label class="text-[13px] text-ink-3">
          메모리 (GB)
          <input v-model.number="form.memory_gb" type="number" min="1" :class="[inputClass, 'mono mt-1']" />
        </label>
        <label class="text-[13px] text-ink-3">
          실행 시간
          <input v-model="form.walltime" :class="[inputClass, 'mono mt-1']" placeholder="02:00:00" />
        </label>
        <label class="text-[13px] text-ink-3">
          해상도
          <select v-model="form.geometry" :class="[inputClass, 'mt-1']">
            <option value="1280x800">1280 × 800</option>
            <option value="1600x900">1600 × 900</option>
            <option value="1920x1080">1920 × 1080</option>
          </select>
        </label>
        <label class="sm:col-span-4 flex items-center gap-2 text-[13.5px] text-ink-2">
          <input v-model="form.exclusive" type="checkbox" />
          노드 독점 (--exclusive) — 같은 노드의 다른 사용자가 이 세션에 접근할 수 없습니다
        </label>
        <Btn variant="primary" :disabled="submitting" @click="launch">
          {{ submitting ? '제출 중…' : `${selected.name} 시작` }}
        </Btn>
      </div>
    </Card>

    <Card title="실행 중 세션" flush>
      <template #title-extra><Fid id="U-IA-04" /></template>
      <ErrorNote :error="errors.list" class="m-4" />
      <div v-if="loading && !sessions.length" class="py-10 text-center text-ink-3">불러오는 중…</div>
      <Empty v-else-if="!sessions.length" text="실행 중인 세션이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'app', label: '앱' },
          { key: 'job', label: 'Job' },
          { key: 'state', label: '상태' },
          { key: 'started', label: '시작' },
          { key: 'act', label: '', width: '180px' },
        ]"
      >
        <tr v-for="s in sessions" :key="s.id" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5">{{ s.app }}</td>
          <td class="px-3.5 py-2.5 mono">{{ s.job_id ?? '—' }}</td>
          <td class="px-3.5 py-2.5">
            <Badge :state="s.is_running ? 'idle' : s.state === 'PENDING' ? 'pending' : 'down'">
              {{ s.state }}
            </Badge>
          </td>
          <td class="px-3.5 py-2.5 mono text-[13px]">
            {{ s.created_at ? new Date(s.created_at).toLocaleString('ko-KR') : '—' }}
          </td>
          <td class="px-3.5 py-2.5 flex gap-2">
            <Btn size="sm" variant="primary" :disabled="!s.is_running" @click="open(s)">접속</Btn>
            <Btn size="sm" variant="danger" :disabled="!!s.terminated_at" @click="terminate(s)">
              종료
            </Btn>
          </td>
        </tr>
      </Table>
      <template #foot>
        세션은 Slurm Job으로 실행됩니다. 상태는 Slurm에서 직접 읽으며, 실행 시간이 끝나면
        자동으로 종료됩니다.
      </template>
    </Card>
  </div>
</template>
