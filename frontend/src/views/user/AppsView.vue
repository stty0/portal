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
import { inputClass } from '@/utils/form'

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

/* --- 해상도 -------------------------------------------------------------
 *
 * 세션 뷰어는 `fixed inset-0`에 캔버스가 `w-full h-full`이고 오버레이는 전부
 * `pointer-events-none`이라 공간을 먹지 않는다(DesktopView.vue) — 즉 **브라우저
 * 뷰포트가 곧 세션 화면**이라 빼야 할 크롬이 없다.
 */
const FIXED_GEOMETRIES = ['1280x800', '1600x900', '1920x1080'] as const

/** 폴백. 창 크기를 못 읽는 환경(SSR·테스트)에서 쓴다. */
const DEFAULT_GEOMETRY = '1280x800'

/**
 * 안전 상한. **비율을 지키며** 이 안으로 줄인다.
 *
 * 처음에는 1920×1080으로 잡았는데 **두 가지가 잘못이었다.**
 * 1. 울트라와이드(3440×1440)를 절반 이하로 깎았다 — "내 화면"이라면서 안 맞았다.
 * 2. 더 나쁘게, **가로·세로를 따로 잘라 화면비가 바뀌었다.** 21:9 창에 16:9
 *    프레임버퍼가 들어가 좌우에 검은 띠가 생기고, 그걸 늘려 보여 주니 흐릿했다.
 *
 * 지금은 창을 그대로 따라간다. 상한은 터무니없는 값(가상 데스크톱 등)만 막는
 * 안전장치다. 느리면 사용자가 아래 고정 해상도를 고르면 된다 —
 * 소프트웨어 렌더링이라 느릴 수 있다는 것은 앱 카드에 이미 적혀 있다.
 */
const MAX_W = 3840
const MAX_H = 2160

/**
 * 지금 브라우저 창에 딱 맞는 해상도.
 *
 * - **화면비를 지킨다.** 상한을 넘으면 가로·세로를 **같은 비율로** 줄인다.
 *   따로 자르면 세션이 창과 다른 모양이 되어 검은 띠가 생긴다.
 * - **`devicePixelRatio`를 곱하지 않는다.** `innerWidth`는 CSS 픽셀이고 그것이
 *   곧 캔버스 크기다. 물리 픽셀(레티나 2배)로 잡으면 원격 데스크톱에는 HiDPI
 *   개념이 없어 **M-Star의 글자·아이콘이 절반 크기로 뜬다.** 선명해지는 대신
 *   못 쓰게 된다.
 * - **8의 배수로 내린다.** 홀수 폭에서 인코딩 아티팩트가 나는 경로가 있다.
 */
function fitGeometry(): string {
  const rawW = window.innerWidth || 0
  const rawH = window.innerHeight || 0
  // 1 이하일 때만 줄인다 — 작은 창을 상한까지 늘리지 않는다.
  const scale = Math.min(1, MAX_W / rawW, MAX_H / rawH)
  const w = Math.floor((rawW * scale) / 8) * 8
  const h = Math.floor((rawH * scale) / 8) * 8
  // 창이 아주 작거나(도킹된 개발자 도구) 값을 못 읽으면 고정값으로 떨어진다.
  if (!Number.isFinite(w) || !Number.isFinite(h) || w < 640 || h < 480) return DEFAULT_GEOMETRY
  return `${w}x${h}`
}

/** 창 크기가 바뀌면 따라 움직인다 — 제출 순간에 한 번 더 읽는다(`launch`). */
const screenFit = ref(fitGeometry())

/**
 * 드롭다운 선택지. 맞춤값이 고정 목록과 겹치면 **항목을 더하지 않고 이름만 바꾼다** —
 * 같은 값이 두 줄로 뜨면 무엇이 다른지 물어보게 된다.
 */
const geometryOptions = computed(() => {
  // 맞춤값은 계산 결과라 리터럴 유니온에 안 들어간다 — 넓혀서 받는다.
  const options: { value: string; label: string; fit: boolean }[] = FIXED_GEOMETRIES.map((value) => ({
    value,
    label: value.replace('x', ' × '),
    fit: value === screenFit.value,
  }))
  if (!options.some((o) => o.fit)) {
    options.unshift({ value: screenFit.value, label: screenFit.value.replace('x', ' × '), fit: true })
  }
  return options
})

const form = ref({
  partition: '',
  account: '',
  cpus: 2,
  memory_gb: 3,
  walltime: '02:00:00',
  // 기본은 **내 화면에 맞춤**이다. 고정값도 그대로 고를 수 있다 — 노트북에서 만든
  // 세션을 큰 모니터에서 다시 열 때는 명시적인 값이 필요하다.
  geometry: fitGeometry(),
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
 * 고를 수 있는가. **잠금이 셋**이라 한 자리에서 묶는다 — 셋은 서로 다른 질문이고
 * **사용자가 할 수 있는 일이 다르다.** 그래서 문구는 카드가 따로 말한다.
 *
 *   ready      실행 방식이 확정됐나        (코드)     → 기다리는 수밖에 없다
 *   installed  이 클러스터에 이미지가 있나 (클러스터) → 관리자에게 설치를 요청한다
 *   allowed    내가 쓸 수 있나             (계정 배정) → 관리자에게 계정 연결을 요청한다
 */
const usable = (a: InteractiveApp) => a.ready && a.installed && a.allowed

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

/**
 * @param refresh `↻ 새로고침`으로 부를 때만 true. 서버가 이미지 목록 캐시를 건너뛰고
 *   클러스터에 다시 물어본다(SSH 왕복 300~430ms). 주기 폴링은 절대 이걸 켜지 않는다 —
 *   5초마다 로그인 노드에 SSH를 열게 된다.
 */
async function load(refresh = false) {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [s, o, a] = await Promise.allSettled([
    sessionApi.list(cid),
    jobApi.options(cid),
    sessionApi.apps(cid, refresh),
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
  // 맞춤을 고른 상태라면 **제출 순간에 다시 읽는다.** resize 이벤트가 안 오는 변화도
  // 있고(모니터 간 창 이동, 브라우저 확대), 세션 해상도는 여기서 확정된다.
  if (form.value.geometry === screenFit.value) {
    screenFit.value = fitGeometry()
    form.value.geometry = screenFit.value
  }
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

/**
 * 창 크기를 따라 '맞춤' 값을 갱신한다.
 *
 * **사용자가 고정 해상도를 골랐으면 건드리지 않는다** — 고른 값이 창 조절 한 번에
 * 바뀌면 고른 의미가 없다. 맞춤에 머물러 있을 때만 따라간다.
 */
function onResize() {
  const next = fitGeometry()
  const wasOnFit = form.value.geometry === screenFit.value
  screenFit.value = next
  if (wasOnFit) form.value.geometry = next
}

/** 제출 직후엔 PENDING이라 붙을 수 없다 — RUNNING으로 바뀌는 것을 폴링으로 본다. */
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  loadAppMeta()
  load()
  window.addEventListener('resize', onResize)
  timer = setInterval(() => {
    if (active.value.length) load()
  }, 5000)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  window.removeEventListener('resize', onResize)
})
// 콜백을 그대로 넘기면 watch가 주는 (신규 id, 이전 id)가 `refresh` 자리에 들어간다.
watch(() => clusters.selectedId, () => load())

</script>

<template>
  <PageHead
    title="인터랙티브 앱"
    :crumbs="['HPC Portal', '작업 환경']"
    :sub="`브라우저에서 여는 GUI 세션 · ${clusters.selectedName}`"
  >
    <template #actions>
      <!-- 사용자가 누른 새로고침만 서버 캐시를 건너뛴다(SSH 재조회). -->
      <Btn @click="load(true)">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <div class="space-y-5">
    <Card title="앱 런처" flush>
      <template #title-extra><Fid id="U-IA-01" /></template>
      <ErrorNote :error="errors.submit" class="m-4" />

      <!--
        **첫 조회는 비어 있는 채로 기다리게 두지 않는다.** 목록은 클러스터에 SSH로
        물어서 만들기 때문에(이미지가 실제로 거기 있는지) 캐시가 없으면 300~430ms가
        걸린다. 그동안 빈 격자만 보이면 "앱이 하나도 없다"로 읽힌다.

        **이미 목록이 있으면 자리를 비우지 않는다** — 새로고침·클러스터 전환에서
        카드가 사라졌다 나타나면 깜빡임이 된다. 그때는 아래 격자를 흐리게만 한다.
      -->
      <div v-if="loading && !apps.length" class="p-4 border-b border-line">
        <div class="grid sm:grid-cols-4 gap-3">
          <div
            v-for="n in 4"
            :key="n"
            class="border border-line rounded-lg p-3.5 animate-pulse"
            aria-hidden="true"
          >
            <div class="h-4 w-2/3 rounded bg-bg" />
            <div class="mt-2 h-3 w-full rounded bg-bg" />
            <div class="mt-1.5 h-3 w-1/2 rounded bg-bg" />
          </div>
        </div>
        <p class="mt-3 text-[13.5px] text-ink-3" role="status">
          앱 목록을 불러오는 중… 클러스터에서 설치된 이미지를 확인하고 있습니다.
        </p>
      </div>

      <!--
        조회가 끝났는데 목록이 비었을 때. 이 줄이 없으면 **빈 격자만 남아** 화면이
        고장 난 것처럼 보인다(로딩 표시는 위에서 이미 끝났다).
      -->
      <Empty
        v-else-if="!apps.length"
        text="이 클러스터에서 쓸 수 있는 앱이 없습니다."
        class="border-b border-line"
      />

      <!-- 카드를 눌러 앱을 고른다. 자원 폼과 제출 버튼은 공유한다. -->
      <div
        v-else
        class="grid sm:grid-cols-4 gap-3 p-4 border-b border-line transition-opacity"
        :class="{ 'opacity-60': loading }"
      >
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
          <p v-if="a.ready && !a.installed" class="mt-2 text-[12.5px] text-ink-2 leading-relaxed">
            이 클러스터에 컨테이너 이미지가 없습니다. 관리자에게 설치를 요청하세요 —
            <b>다른 클러스터에서는 쓸 수 있을 수 있습니다.</b>
          </p>
          <p v-else-if="a.ready && !a.allowed" class="mt-2 text-[12.5px] text-ink-2 leading-relaxed">
            <b class="mono">{{ a.accounts.join(', ') }}</b> 계정에 소속된 사용자만 사용할 수
            있습니다. 관리자에게 계정 연결을 요청하세요.
          </p>
          <Chip v-if="!a.ready" tone="gray" class="mt-2">
            {{ a.note ? '포털 밖에서 사용' : '준비 중' }}
          </Chip>
          <Chip v-else-if="!a.installed" tone="gray" class="mt-2">이 클러스터에 없음</Chip>
          <Chip v-else-if="!a.allowed" tone="gray" class="mt-2">계정 제한</Chip>
          <Chip v-else-if="selectedApp === a.id" tone="brand" class="mt-2">선택됨</Chip>
        </button>
      </div>

      <!--
        폼 값이 그대로 sbatch 자원이 된다 (Job 제출과 같은 규칙).

        **입력 6개를 한 줄에 둔다** — 열 수가 입력 개수와 같아야 한다. 5열이던 동안
        해상도만 다음 줄로 넘어가 폼이 두 동강 나 보였다. 입력을 늘리거나 줄이면
        `lg:grid-cols-6`도 함께 고친다.
        좁은 화면에서는 3열(2줄)로 접는다 — 6열을 640px에 밀어 넣으면 '메모리 (GB)'
        같은 라벨이 줄바꿈되어 오히려 읽기 어렵다.
      -->
      <div class="p-4 grid sm:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
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
            <option v-for="g in geometryOptions" :key="g.value" :value="g.value">
              {{ g.label }}{{ g.fit ? ' — 내 화면' : '' }}
            </option>
          </select>
        </label>
        <!-- 남는 칸을 다 먹어 제출 버튼을 오른쪽 끝으로 민다(열 수 - 1). -->
        <label class="sm:col-span-2 lg:col-span-5 flex items-center gap-2 text-[13.5px] text-ink-2">
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
