<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionApi, type InteractiveApp, type Session } from '@/api/sessions'
import { jobApi } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import { hideBrokenIcon, useAppMeta } from '@/utils/appMeta'
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
  account: '',
  cpus: 2,
  memory_gb: 3,
  walltime: '02:00:00',
  geometry: '1280x800',
  exclusive: false,
})

/**
 * 앱 목록은 **백엔드 카탈로그**가 준다. 어떤 이미지를 쓰는지는 앱이 알고, 클러스터는
 * 이미지가 있는 저장소만 갖는다 — 여기에 목록을 또 두면 실행 가능한 앱이 무엇인지에
 * 대해 앞뒤가 갈린다.
 */
const apps = ref<InteractiveApp[]>([])
// 아이콘·벤더·버전은 관리자가 등록한 값이다(A-OP-02). 없으면 카드가 그냥 지금과 같다.
const { loadAppMeta, appMeta, appMetaLine } = useAppMeta('interactive')
const selectedApp = ref('desktop')
const selected = computed(
  () => apps.value.find((a) => a.id === selectedApp.value) ?? apps.value[0] ?? null,
)

/**
 * 고를 수 있는가. **잠금이 두 가지**라 한 자리에서 묶는다 —
 * `ready`는 포털이 아직 제공하지 않는 앱, `allowed`는 관리자가 정한 계정 배정에서
 * 빠진 앱이다. 사용자가 할 수 있는 일이 다르므로 문구는 카드가 따로 말한다.
 */
const usable = (a: InteractiveApp) => a.ready && a.allowed

/**
 * 계정 선택지. **배정된 앱이면 그 계정만** 남긴다 — 고를 수 없는 값을 보여주면
 * 제출에서 거부당하고 이유는 화면에 없다.
 */
const accounts = computed(() => {
  const mine = allAccounts.value
  const only = selected.value?.accounts ?? []
  return only.length ? mine.filter((a) => only.includes(a)) : mine
})
const allAccounts = ref<string[]>([])

// 앱을 바꾸면 고를 수 있는 계정이 달라진다 — 남아 있으면 엉뚱한 계정으로 제출된다.
watch(accounts, (list) => {
  if (form.value.account && !list.includes(form.value.account)) form.value.account = ''
})

const active = computed(() => sessions.value.filter((s) => !s.terminated_at && s.state !== 'ENDED'))

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [s, o, a] = await Promise.allSettled([
    sessionApi.list(cid),
    jobApi.options(cid),
    sessionApi.apps(cid),
  ])
  sessions.value = s.status === 'fulfilled' ? s.value : []
  errors.value.list = s.status === 'rejected' ? s.reason : null
  if (a.status === 'fulfilled') {
    apps.value = a.value
    // 고른 앱이 목록에 없거나 잠겼으면(카탈로그 변경·계정 배정) 쓸 수 있는 첫 앱으로 되돌린다.
    if (!a.value.some((x) => x.id === selectedApp.value && usable(x))) {
      selectedApp.value = a.value.find(usable)?.id ?? ''
    }
  }
  if (o.status === 'fulfilled') {
    partitions.value = o.value.partitions ?? []
    allAccounts.value = o.value.accounts ?? []
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
      // 비우면 서버가 정한다 — 배정된 앱이면 그 계정, 아니면 Slurm 기본 계정이다.
      account: form.value.account || null,
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

/**
 * 세션에 붙는다. **어느 앱이든 새 탭으로 연다.**
 *
 * 인터랙티브 앱은 화면 전체와 키보드를 통째로 쓴다 — 데스크톱·ParaView는 창 관리자와
 * 단축키가 있고, JupyterLab도 자기 단축키 체계를 갖는다. 포털 레이아웃(사이드바·톱바)
 * 안에 끼워 두면 화면도 좁고 단축키도 서로 먹는다. 세션을 여러 개 동시에 띄우고
 * 오가기도 탭 쪽이 편하다.
 *
 * 어디로 보낼지는 카탈로그의 `transport`가 정한다 — 화면이 앱 id로 분기하지 않는다.
 *   vnc  — 포털의 원격 데스크톱 화면(`/apps/{sid}`). RFB 중계는 그 페이지가 한다.
 *   http — 포털이 리버스 프록시하는 앱 주소(`/api/v1/session-apps/{job_id}/`).
 *
 * 인증은 둘 다 **쿠키가 나른다** — 같은 오리진이라 새 탭에도 그대로 실린다.
 */
function open(s: Session) {
  const app = apps.value.find((a) => a.id === s.app)
  const url =
    app?.transport === 'http' && s.job_id
      ? `/api/v1/session-apps/${s.job_id}/`
      : router.resolve({ name: 'desktop', params: { sid: s.id } }).href
  window.open(url, '_blank', 'noopener')
}

/** 제출 직후엔 PENDING이라 붙을 수 없다 — RUNNING으로 바뀌는 것을 폴링으로 본다. */
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  loadAppMeta()
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
          v-for="a in apps"
          :key="a.id"
          type="button"
          :disabled="!usable(a)"
          class="text-left border rounded-lg p-3.5 transition-colors"
          :class="[
            !usable(a)
              ? 'border-line opacity-60 cursor-not-allowed'
              : selectedApp === a.id
                ? 'border-brand-700 ring-2 ring-brand-700/25 bg-bg'
                : 'border-line hover:border-brand-500',
          ]"
          @click="selectedApp = a.id"
        >
          <div class="flex items-center gap-2">
            <img
              v-if="appMeta(a.id)?.icon_url" :src="appMeta(a.id)!.icon_url!" alt=""
              class="w-6 h-6 rounded object-contain shrink-0" @error="hideBrokenIcon"
            />
            <b class="text-[15px]">{{ a.name }}</b>
            <Fid :id="a.fid" />
          </div>
          <p v-if="appMetaLine(a.id)" class="mt-0.5 text-[12.5px] text-ink-3">{{ appMetaLine(a.id) }}</p>
          <p class="mt-1 text-[13px] text-ink-3">{{ a.description }}</p>
          <!--
            안내가 있는 앱은 "준비 중"이 아니다 — 포털이 호스팅하지 않기로 정한 것이라
            기다려도 생기지 않는다(VS Code = Remote-SSH). 그 차이를 카드가 말해야 한다.
          -->
          <p v-if="a.note" class="mt-2 text-[12.5px] text-ink-2 leading-relaxed">{{ a.note }}</p>
          <!--
            **계정 때문에 잠긴 앱은 숨기지 않는다.** 숨기면 사용자는 그 앱의 존재를
            모른 채 "안 보인다"고 묻게 된다 — 누구에게 무엇을 요청해야 하는지 적어 준다.
          -->
          <p v-if="a.ready && !a.allowed" class="mt-2 text-[12.5px] text-ink-2 leading-relaxed">
            <b class="mono">{{ a.accounts.join(', ') }}</b> 계정에 소속된 사용자만 사용할 수
            있습니다. 관리자에게 계정 연결을 요청하세요.
          </p>
          <Chip v-if="!a.ready" tone="gray" class="mt-2">
            {{ a.note ? '포털 밖에서 사용' : '준비 중' }}
          </Chip>
          <Chip v-else-if="!a.allowed" tone="gray" class="mt-2">계정 제한</Chip>
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
        <!--
          계정을 고르면 그 계정에 Job이 붙는다(과금·fairshare가 여기를 본다).
          비우면 서버가 정한다 — 계정이 배정된 앱이면 그 계정, 아니면 Slurm 기본 계정이다.
          선택지가 없어도 칸을 남긴다. 빼면 아래 폼이 밀려 배치가 흔들린다.
        -->
        <label class="text-[13px] text-ink-3">
          계정
          <select
            v-if="accounts.length"
            v-model="form.account"
            :class="[inputClass, 'mono mt-1']"
          >
            <option value="">기본 계정</option>
            <option v-for="a in accounts" :key="a" :value="a">{{ a }}</option>
          </select>
          <input v-else disabled :class="[inputClass, 'mono mt-1 bg-bg']" value="기본 계정" />
        </label>
        <!-- 노드 독점이면 Slurm이 노드 전체를 할당한다 — 여기서 정할 것이 없다 -->
        <label class="text-[13px] text-ink-3" :class="{ 'opacity-50': form.exclusive }">
          CPU
          <input
            v-if="!form.exclusive"
            v-model.number="form.cpus" type="number" min="1"
            :class="[inputClass, 'mono mt-1']"
          />
          <input v-else disabled :class="[inputClass, 'mono mt-1 bg-bg']" value="노드 전체" />
        </label>
        <label class="text-[13px] text-ink-3" :class="{ 'opacity-50': form.exclusive }">
          메모리 (GB)
          <input
            v-if="!form.exclusive"
            v-model.number="form.memory_gb" type="number" min="1"
            :class="[inputClass, 'mono mt-1']"
          />
          <input v-else disabled :class="[inputClass, 'mono mt-1 bg-bg']" value="노드 전체" />
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
        <label class="sm:col-span-3 flex items-center gap-2 text-[13.5px] text-ink-2">
          <input v-model="form.exclusive" type="checkbox" />
          노드 독점 (--exclusive) — 워커 노드를 통째로 씁니다. CPU·메모리를 노드 전체로
          잡고 다른 사용자의 작업이 배정되지 않아 렌더링 성능이 안정적이지만, 대기열이
          길어질 수 있습니다
        </label>
        <Btn
          variant="primary"
          :disabled="submitting || !selected || !usable(selected)"
          @click="launch"
        >
          {{ submitting ? '제출 중…' : `${selected?.name ?? '앱'} 시작` }}
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
