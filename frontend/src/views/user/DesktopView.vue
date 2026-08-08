<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RFB from '@novnc/novnc'
import { sessionApi, type Session } from '@/api/sessions'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'

/**
 * SCR-06 원격 데스크톱 화면 (U-IA-02).
 *
 * websockify를 쓰지 않는다 — 백엔드가 WebSocket↔TCP 변환을 하고 noVNC의 RFB가 그 위에
 * 바로 붙는다. **접속 위치(워커 노드·포트)는 브라우저에 오지 않는다.** 세션 ID만 보내면
 * 서버가 소유자를 확인하고 터널을 연다.
 */
const route = useRoute()
const router = useRouter()
const sid = Number(route.params.sid)

const screen = ref<HTMLDivElement | null>(null)
const rfb = shallowRef<InstanceType<typeof RFB> | null>(null)
const session = ref<Session | null>(null)
const state = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')
const error = ref<unknown>(null)
const closeReason = ref('')

/** 우리가 끊은 것을 세션 종료로 오해하면 안 된다(연결 끊기 버튼·인증 실패·화면 이탈). */
let expected = false
/** 재연결하면 이전 연결의 뒤늦은 disconnect 이벤트가 따라온다 — 세대로 걸러낸다. */
let generation = 0
/** 화면을 떠난 뒤에 라우팅하거나 상태를 건드리지 않기 위한 표시. */
let disposed = false

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function connect() {
  if (!screen.value) return
  disconnect()
  const gen = ++generation
  expected = false
  state.value = 'connecting'
  error.value = null
  closeReason.value = ''

  try {
    session.value = await sessionApi.get(sid)
    // 비밀번호만 받는다. 호스트·포트는 응답에 없다.
    const info = await sessionApi.connection(sid)
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    const client = new RFB(
      screen.value,
      `${scheme}://${location.host}/api/v1/sessions/${sid}/connect`,
      {
        // 인증은 HttpOnly 쿠키가 나른다(웹 터미널과 같은 규칙) — JS가 토큰을 읽지 않는다.
        credentials: { password: info.password ?? '' },
      },
    )
    client.scaleViewport = true
    client.resizeSession = false
    client.addEventListener('connect', () => {
      state.value = 'open'
    })
    client.addEventListener('disconnect', () => {
      if (gen !== generation) return // 이미 갈아탄 연결의 뒷정리
      state.value = 'closed'
      if (expected) {
        closeReason.value = '연결을 끊었습니다.'
        return
      }
      closeReason.value = '연결이 끊어졌습니다. 세션 상태를 확인하는 중…'
      confirmSessionEnded()
    })
    client.addEventListener('securityfailure', () => {
      // 곧 이어질 disconnect가 이 메시지를 덮어쓰지 않게 한다.
      expected = true
      state.value = 'closed'
      closeReason.value = 'VNC 인증에 실패했습니다.'
    })
    rfb.value = client
  } catch (e) {
    state.value = 'closed'
    error.value = e
  }
}

function disconnect() {
  expected = true
  rfb.value?.disconnect()
  rfb.value = null
}

/**
 * 끊긴 이유를 **Slurm 상태로** 확인한다. 웹소켓이 끊겼다는 사실만으로는 "세션이 끝났다"와
 * "잠깐 네트워크가 끊겼다"를 구분할 수 없다 — 앱을 닫으면 Job이 함께 끝나므로(U-IA-04)
 * 끝난 것이 확인되면 목록으로 돌려보내고, 아직 살아 있으면 재연결 버튼을 남긴다.
 *
 * Job 상태가 RUNNING에서 넘어가는 데 몇 초 걸리므로 한 번 보고 단정하지 않는다.
 */
async function confirmSessionEnded() {
  for (let attempt = 0; attempt < 4 && !disposed; attempt++) {
    try {
      const s = await sessionApi.get(sid)
      session.value = s
      if (!s.is_running) {
        closeReason.value = '세션이 종료되었습니다. 목록으로 돌아갑니다…'
        await sleep(1500)
        if (!disposed) router.push({ name: 'apps' })
        return
      }
    } catch {
      // 조회 실패로 "끝났다"고 단정하지 않는다 — 화면에 남겨 두고 사용자가 판단하게 한다.
    }
    await sleep(2000)
  }
  if (!disposed) {
    closeReason.value = '연결이 끊어졌습니다. 세션은 아직 실행 중입니다 — 재연결할 수 있습니다.'
  }
}

/** 클립보드·조합키가 브라우저에 먹히지 않게 데스크톱으로 넘긴다. */
function sendCtrlAltDel() {
  rfb.value?.sendCtrlAltDel()
}

/**
 * 화면을 브라우저 창 전체로 넓힌다. 컨테이너 크기만 바꾸면 되고 재연결은 필요 없다 —
 * noVNC가 컨테이너를 ResizeObserver로 보고 있어 `scaleViewport`가 알아서 다시 맞춘다.
 */
const maximized = ref(false)

onMounted(connect)
onBeforeUnmount(() => {
  disposed = true
  disconnect()
})
</script>

<template>
  <PageHead
    title="원격 데스크톱"
    :crumbs="['HPC Portal', '작업 환경', '인터랙티브 앱']"
    :sub="session ? `Job ${session.job_id} · ${session.state}` : `세션 #${sid}`"
  >
    <template #actions>
      <Btn @click="router.push({ name: 'apps' })">목록</Btn>
      <Btn :disabled="state !== 'open'" @click="sendCtrlAltDel">Ctrl+Alt+Del</Btn>
      <Btn v-if="state !== 'open'" variant="primary" @click="connect">재연결</Btn>
      <Btn v-else variant="danger" @click="disconnect">연결 끊기</Btn>
      <Btn @click="maximized = true">최대화</Btn>
    </template>
  </PageHead>

  <Card title="화면" flush>
    <template #title-extra><Fid id="U-IA-02" /></template>
    <template #head>
      <Badge :state="state === 'open' ? 'idle' : state === 'connecting' ? 'pending' : 'down'">
        {{ state === 'open' ? '연결됨' : state === 'connecting' ? '연결 중' : '끊김' }}
      </Badge>
    </template>

    <ErrorNote :error="error" class="m-4" />
    <p v-if="closeReason" class="px-4 py-2 text-[13.5px] text-ink-3">{{ closeReason }}</p>

    <!-- noVNC가 이 요소 안에 캔버스를 만든다 -->
    <div
      ref="screen"
      class="bg-side-bg overflow-hidden"
      :class="maximized ? 'fixed inset-0 z-50' : 'h-[75vh] rounded-b-card'"
    />
    <!-- 최대화 중에는 페이지 헤더가 가려지므로 조작 버튼을 화면 위에 띄운다. -->
    <div v-if="maximized" class="fixed top-3 right-3 z-50 flex gap-2">
      <Btn size="sm" :disabled="state !== 'open'" @click="sendCtrlAltDel">Ctrl+Alt+Del</Btn>
      <Btn size="sm" @click="maximized = false">작게</Btn>
    </div>

    <template #foot>
      본인 세션에만 접속할 수 있습니다 — 서버가 소유자를 확인한 뒤 워커 노드로 터널을 엽니다.
      접속 위치는 브라우저에 전달되지 않습니다.
    </template>
  </Card>
</template>
