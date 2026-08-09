import { api } from './client'
import type { OkResponse } from '@/types/api'

/** 인터랙티브 세션 (U-IA-01·02·04). 세션은 Slurm 배치 Job이다. */
export interface Session {
  id: number
  cluster_id: number
  app: string
  job_id: string | null
  /** Slurm에서 읽은 실제 상태 — 포털 DB가 아니라 이쪽이 권위 있는 출처다. */
  state: string
  is_running: boolean
  created_at: string | null
  terminated_at: string | null
}

export interface SessionCreate {
  app?: string
  partition?: string | null
  account?: string | null
  qos?: string | null
  cpus?: number | null
  memory_gb?: number | null
  walltime?: string | null
  geometry?: string
  exclusive?: boolean
}

/**
 * RFB 핸드셰이크에 필요한 값만 온다.
 * **접속 위치(호스트·포트)는 응답에 없다** — 백엔드만 알고 터널을 연다.
 */
export interface SessionConnectInfo {
  password: string | null
  geometry: string | null
}

/** U-IA-01 런처의 선택지. 목록은 백엔드 카탈로그가 단일 출처다. */
export interface InteractiveApp {
  id: string
  name: string
  description: string
  /** 기능 정의서 ID — 화면의 Fid 매핑에 쓴다. */
  fid: string
  /** 아직 제공하지 않는 앱은 보여주되 고를 수 없다. */
  ready: boolean
  /**
   * 접속 방식. `vnc`는 원격 데스크톱 화면(RFB 중계), `http`는 포털이 프록시하는 웹 앱이다.
   * **화면이 앱 id로 분기하지 않는다** — 앱을 늘릴 때마다 화면을 고쳐야 하기 때문이다.
   */
  transport: 'vnc' | 'http'
  /** 실행할 수 없는 앱의 안내(예: VS Code는 Remote-SSH를 쓴다). 비어 있으면 표시하지 않는다. */
  note: string
  /**
   * 이 사용자가 쓸 수 있는가. `ready`와 **다른 잠금**이다 — 앱은 준비됐지만
   * 관리자가 정한 계정 배정에서 빠진 경우다.
   */
  allowed: boolean
  /** 이 앱에 배정된 계정. 비어 있으면 전원 허용이라 화면이 아무 말도 하지 않는다. */
  accounts: string[]
}

export const sessionApi = {
  // 앱마다 쓸 수 있는 계정이 다를 수 있고 계정은 클러스터별 slurmdbd 소유다 —
  // 그래서 목록이 클러스터에 매인다.
  apps: (cid: number) => api.get<InteractiveApp[]>(`/clusters/${cid}/interactive-apps`),
  create: (cid: number, payload: SessionCreate) =>
    api.post<Session>(`/clusters/${cid}/sessions`, payload),
  list: (cid: number) => api.get<Session[]>(`/clusters/${cid}/sessions`),
  get: (sid: number) => api.get<Session>(`/sessions/${sid}`),
  connection: (sid: number) => api.get<SessionConnectInfo>(`/sessions/${sid}/connection`),
  terminate: (sid: number) => api.del<OkResponse>(`/sessions/${sid}`),
}
