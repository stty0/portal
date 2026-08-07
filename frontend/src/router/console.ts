import { computed, type ComputedRef } from 'vue'
import { useRoute } from 'vue-router'

/**
 * 콘솔 — 사이드바 하나에 담기는 화면 묶음.
 *
 * 관리자 화면은 성격이 둘로 갈린다. `portal`은 포털 전체 설정이고, `cluster`는 **톱바에서
 * 고른 클러스터 하나**에만 적용된다. 한 사이드바에 섞여 있으면 지금 보는 화면이 선택
 * 클러스터를 따르는지 알 수 없다 — 비용/Billing에서 클러스터를 바꿔도 아무 일이 안 나는데
 * 화면은 그 사실을 말해 주지 않았다.
 *
 * **인가와는 별개다.** 권한은 `meta.admin`이 정하고 라우터 가드가 강제한다. 여기서 재활용하면
 * 메뉴를 옮기다가 권한이 열린다.
 */
export type Console = 'portal' | 'cluster' | 'user'

/** 콘솔을 전환할 때 착지할 화면. */
export const CONSOLE_HOME: Record<Console, string> = {
  portal: '/admin/clusters',
  cluster: '/admin/dashboard',
  user: '/cluster',
}

export const CONSOLE_LABEL: Record<Console, string> = {
  portal: '포탈 설정',
  cluster: '클러스터 관리',
  user: '사용자 포털',
}

/**
 * 현재 콘솔. **라우트에서 파생한다 — 따로 저장하지 않는다.**
 *
 * `/admin/billing`을 북마크로 열면 저절로 포탈 설정 셸이어야 한다. 별도 상태로 들고 있으면
 * 새로고침·딥링크에서 어긋난다.
 */
export function useConsole(): ComputedRef<Console> {
  const route = useRoute()
  return computed(() => (route.meta.console as Console | undefined) ?? 'user')
}
