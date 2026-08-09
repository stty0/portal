import { ref } from 'vue'
import { opsApi, type AppCatalog } from '@/api/ops'

/**
 * 앱 카탈로그(A-OP-02) 메타데이터를 런처 카드에 얹기 위한 조회기.
 *
 * **실행 카탈로그가 정본이고 여기서 얹는 것은 표시용뿐이다.** 앱 목록·실행 가능 여부는
 * 백엔드 코드 카탈로그(`session_apps.py`·`batch_apps.py`)가 그대로 결정하고, 관리자가
 * 등록한 아이콘·벤더·버전만 `(kind, app_id)`로 붙인다. 등록이 없으면 아무것도 붙지
 * 않고 카드는 코드의 이름·설명을 그대로 쓴다.
 */

//: 모듈 스코프 — 두 런처(인터랙티브·Batch)가 같은 목록을 두 번 받지 않는다.
const catalog = ref<AppCatalog[]>([])
let loaded = false

export function useAppMeta(kind: AppCatalog['kind']) {
  async function loadAppMeta() {
    if (loaded) return
    try {
      catalog.value = await opsApi.apps()
      loaded = true
    } catch {
      // 메타데이터는 부가 정보다 — 실패해도 런처는 코드 카탈로그로 그대로 뜬다.
      // loaded를 세우지 않으므로 다음 진입에서 다시 시도한다.
      catalog.value = []
    }
  }

  const appMeta = (appId: string): AppCatalog | null =>
    catalog.value.find((a) => a.kind === kind && a.app_id === appId) ?? null

  /** "벤더 · v버전" — 둘 중 등록된 것만 남긴다. */
  function appMetaLine(appId: string): string {
    const m = appMeta(appId)
    if (!m) return ''
    const version = m.version?.replace(/^v/i, '')
    return [m.vendor, version && `v${version}`].filter(Boolean).join(' · ')
  }

  return { loadAppMeta, appMeta, appMetaLine }
}

/** 죽은 URL이 깨진 이미지 아이콘으로 남지 않게 한다 — 아이콘은 없어도 그만이다. */
export function hideBrokenIcon(e: Event) {
  ;(e.target as HTMLImageElement).style.display = 'none'
}
