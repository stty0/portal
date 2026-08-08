<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useClusterStore } from '@/stores/cluster'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'

/**
 * SCR-08 웹 터미널 (U-SH-01).
 *
 * 서버가 로그인 노드에 `sudo -u <본인>`으로 PTY를 열고 웹소켓으로 중계한다.
 * 인증 토큰은 **subprotocol**로 보낸다 — 브라우저 웹소켓은 헤더를 못 붙이고,
 * 쿼리스트링에 실으면 접근 로그에 남는다.
 */
const clusters = useClusterStore()
const host = ref<HTMLDivElement | null>(null)
const state = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')

const term = shallowRef<Terminal | null>(null)
const fit = shallowRef<FitAddon | null>(null)
const socket = shallowRef<WebSocket | null>(null)

function sendResize() {
  const t = term.value
  if (t && socket.value?.readyState === WebSocket.OPEN) {
    socket.value.send(JSON.stringify({ resize: [t.cols, t.rows] }))
  }
}

function onWindowResize() {
  fit.value?.fit()
  sendResize()
}

function connect() {
  const cid = clusters.selectedId
  if (!cid || !term.value) return

  disconnect()
  state.value = 'connecting'
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  // 인증은 HttpOnly 쿠키가 나른다 — 같은 오리진이면 handshake에 자동으로 실린다.
  // 예전에는 토큰을 subprotocol로 보냈는데, 그러려면 JS가 토큰을 읽을 수 있어야 했다.
  const ws = new WebSocket(`${scheme}://${location.host}/api/v1/clusters/${cid}/terminal`)
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    state.value = 'open'
    fit.value?.fit()
    sendResize()
    term.value?.focus()
  }
  ws.onmessage = (event) => {
    const data = event.data
    if (data instanceof ArrayBuffer) term.value?.write(new Uint8Array(data))
    else term.value?.write(String(data))
  }
  ws.onclose = (event) => {
    state.value = 'closed'
    // 서버가 사유를 코드로만 알려주는 경우가 있어 화면에도 남긴다.
    const reason: Record<number, string> = {
      4401: '인증에 실패했습니다. 다시 로그인하세요.',
      4403: '비활성화된 계정입니다.',
      4400: '터미널을 열 수 없습니다.',
      4500: '서버 오류로 터미널을 열 수 없습니다.',
    }
    term.value?.write(`\r\n\x1b[33m[연결 종료] ${reason[event.code] ?? ''}\x1b[0m\r\n`)
  }
  socket.value = ws
}

function disconnect() {
  socket.value?.close()
  socket.value = null
}

onMounted(() => {
  const t = new Terminal({
    fontFamily: 'JetBrains Mono, D2Coding, Consolas, monospace',
    fontSize: 13,
    cursorBlink: true,
    // 사이드바 네이비와 맞춰 화면 전체가 한 덩어리로 보이게 한다.
    theme: { background: '#131a3a', foreground: '#e6e9f5', cursor: '#e6e9f5' },
  })
  const addon = new FitAddon()
  t.loadAddon(addon)
  if (host.value) t.open(host.value)
  addon.fit()
  t.onData((data) => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ i: data }))
    }
  })
  t.onResize(() => sendResize())
  term.value = t
  fit.value = addon
  window.addEventListener('resize', onWindowResize)
  connect()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  disconnect()
  term.value?.dispose()
})

// 클러스터를 바꾸면 그 노드로 다시 붙는다.
watch(() => clusters.selectedId, connect)
</script>

<template>
  <PageHead
    title="웹 터미널"
    :crumbs="['HPC Portal', '작업 환경']"
    :sub="`로그인 노드 셸 (SSH PTY) · ${clusters.selectedName}`"
  >
    <template #actions>
      <Btn v-if="state !== 'open'" variant="primary" @click="connect">재연결</Btn>
      <Btn v-else @click="disconnect">연결 종료</Btn>
    </template>
  </PageHead>

  <Card title="터미널" flush>
    <template #title-extra><Fid id="U-SH-01" /></template>
    <template #head>
      <Badge :state="state === 'open' ? 'idle' : state === 'connecting' ? 'pending' : 'down'">
        {{ state === 'open' ? '연결됨' : state === 'connecting' ? '연결 중' : '끊김' }}
      </Badge>
    </template>
    <div ref="host" class="h-[70vh] p-3 bg-side-bg rounded-b-card" />
    <template #foot>
      본인 계정으로 접속합니다 — 서버가 인증된 사용자로 강제하며, 세션 시작·종료는 감사
      로그에 기록됩니다.
    </template>
  </Card>
</template>
