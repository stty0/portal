/**
 * 배포 후 남아 있는 옛 탭 복구.
 *
 * 새 빌드가 올라가면 이전 해시의 청크 파일이 사라진다. 그때 열려 있던 탭이
 * 지연 로딩(동적 import)을 시도하면 404가 나고, 화면은 **아무 반응 없이 멈춘다**
 * (라우팅이 취소될 뿐 오류 화면도 뜨지 않는다). 사용자가 원인을 알 방법이 없으므로
 * 한 번만 자동 새로고침해 새 번들을 받아오게 한다.
 */

const KEY = 'hpc-chunk-reload-at'
/** 새 배포에서도 계속 실패하면 무한 새로고침이 된다 — 쿨다운으로 1회만 시도한다. */
const COOLDOWN_MS = 10_000

const CHUNK_ERROR = /dynamically imported module|Importing a module script failed|Loading chunk|ChunkLoadError|error loading dynamically imported/i

export function isChunkLoadError(error: unknown): boolean {
  const message = String((error as Error | undefined)?.message ?? error ?? '')
  return CHUNK_ERROR.test(message)
}

export function reloadForStaleChunk(): boolean {
  const last = Number(sessionStorage.getItem(KEY) ?? 0)
  if (Date.now() - last < COOLDOWN_MS) return false
  sessionStorage.setItem(KEY, String(Date.now()))
  window.location.reload()
  return true
}

/** 라우터 오류 + Vite 프리로드 오류 양쪽을 잡는다. */
export function installChunkReload(router: { onError: (h: (e: unknown) => void) => void }): void {
  router.onError((error) => {
    if (isChunkLoadError(error)) reloadForStaleChunk()
  })
  window.addEventListener('vite:preloadError', () => {
    reloadForStaleChunk()
  })
}
