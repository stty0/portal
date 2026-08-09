<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import RFB from '@novnc/novnc'
import { sessionApi, type Session } from '@/api/sessions'
import { PortalApiError } from '@/api/client'
import Btn from '@/components/ui/Btn.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'

/**
 * SCR-06 원격 데스크톱 화면 (U-IA-02).
 *
 * websockify를 쓰지 않는다 — 백엔드가 WebSocket↔TCP 변환을 하고 noVNC의 RFB가 그 위에
 * 바로 붙는다. **접속 위치(워커 노드·포트)는 브라우저에 오지 않는다.** 세션 ID만 보내면
 * 서버가 소유자를 확인하고 터널을 연다.
 */
const route = useRoute()
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

/**
 * 접속 정보가 준비될 때까지 기다린다.
 *
 * **Slurm의 RUNNING과 "붙을 수 있다"는 같지 않다.** Job이 시작된 뒤 컨테이너가 Xvnc와
 * 데스크톱을 띄우고 `connection.json`을 쓰기까지 10~20초가 더 걸린다(실측). 그 사이의
 * 접속은 실패가 아니라 **기다릴 일**이라 서버가 `reason: "starting"`으로 알려 준다.
 *
 * 그걸 그대로 오류로 띄우면 사용자는 세션이 깨진 줄 알고 다시 만든다 — 실제로 그랬다.
 */
async function waitForConnection(gen: number) {
  for (let attempt = 0; attempt < 40; attempt++) {
    if (disposed || gen !== generation) return null
    try {
      return await sessionApi.connection(sid)
    } catch (e) {
      const starting =
        e instanceof PortalApiError &&
        (e.detail as { reason?: string } | null)?.reason === 'starting'
      if (!starting) throw e
      closeReason.value = `세션이 시작되는 중입니다… (${attempt * 2}초)`
      await sleep(2000)
    }
  }
  throw new Error('세션이 준비되지 않았습니다. 잠시 뒤 재연결해 보세요.')
}

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
    const info = await waitForConnection(gen)
    if (info === null) return // 화면을 떠났거나 새 연결로 갈아탔다
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
        if (!disposed) leave()
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
 * 탭을 닫는다. 목록에서 새 탭으로 연 화면이라 `window.close()`가 먹는다.
 *
 * 주소를 직접 열었거나 브라우저가 거부하면 안 닫힌다 — 그때는 **전체 새로고침으로**
 * 목록으로 보낸다. SPA 내부 이동으로 가면 이 라우트가 `bare`라 사이드바 없는 목록이 뜬다.
 */
function leave() {
  window.close()
  setTimeout(() => {
    if (!disposed) window.location.href = '/apps'
  }, 150)
}

onMounted(connect)
onBeforeUnmount(() => {
  disposed = true
  disconnect()
})
</script>

<template>
  <!--
    새 탭으로 여는 화면이라 **VNC가 창을 통째로 쓴다**(JupyterLab이 자기 탭을 꽉 채우는
    것과 같다). 사이드바·톱바는 `route.meta.bare`로 App.vue가 이미 빼고, 여기서는
    카드·머리말도 두지 않는다 — 데스크톱 안에 또 데스크톱 껍데기를 그릴 이유가 없다.
    조작 버튼은 화면 위에 띄우고, 마우스를 올릴 때만 진하게 한다.
  -->
  <div class="fixed inset-0 bg-side-bg">
    <!-- noVNC가 이 요소 안에 캔버스를 만든다 -->
    <div ref="screen" class="w-full h-full" />

    <!--
      **오버레이는 클릭을 가로채면 안 된다.** 앱의 메뉴·툴바는 화면 맨 위에 있어서
      폭 전체를 덮는 띠를 두면 그 높이의 클릭이 전부 여기로 온다(실측: ParaView의
      File·Edit 메뉴를 누를 수 없었다).

      그래서 바깥은 `pointer-events-none`이고 **버튼만** 이벤트를 받는다. 표시용 글자는
      끝까지 투명하게 지나간다.
    -->
    <div
      class="pointer-events-none select-none fixed top-1 left-2 z-10 mono text-[12px]
             text-side-ink opacity-40"
    >
      Job {{ session?.job_id ?? sid }} · {{ session?.state ?? '…' }}
    </div>

    <!--
      조작 버튼은 **아래쪽 구석**에 둔다. 메뉴·툴바가 있는 위쪽을 피하고, 막는 넓이도
      버튼 자기 크기뿐이다. 평소에는 흐리게 두고 마우스를 올릴 때만 진해진다.
    -->
    <div class="pointer-events-none fixed bottom-3 right-3 z-10 flex gap-2">
      <Btn
        size="sm"
        class="pointer-events-auto opacity-30 hover:opacity-100 transition-opacity"
        :disabled="state !== 'open'"
        @click="sendCtrlAltDel"
      >Ctrl+Alt+Del</Btn>
      <!-- 끊긴 상태에서는 화면이 죽어 있으므로 가려도 상관없다 — 진하게 보여준다. -->
      <Btn
        v-if="state !== 'open'"
        size="sm"
        variant="primary"
        class="pointer-events-auto"
        @click="connect"
      >재연결</Btn>
    </div>

    <!-- 준비 중·오류. 이때는 화면이 아직 없거나 죽어 있다. -->
    <div
      v-if="error || (closeReason && state !== 'open')"
      class="pointer-events-none fixed inset-x-0 top-16 z-10 flex justify-center px-4"
    >
      <div class="max-w-lg w-full rounded-lg bg-surface shadow-pop px-4 py-3">
        <ErrorNote :error="error" />
        <p v-if="closeReason" class="text-[13.5px] text-ink-2">{{ closeReason }}</p>
      </div>
    </div>
  </div>
</template>
