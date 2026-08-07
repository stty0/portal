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
}

export const sessionApi = {
  apps: () => api.get<InteractiveApp[]>('/interactive-apps'),
  create: (cid: number, payload: SessionCreate) =>
    api.post<Session>(`/clusters/${cid}/sessions`, payload),
  list: (cid: number) => api.get<Session[]>(`/clusters/${cid}/sessions`),
  get: (sid: number) => api.get<Session>(`/sessions/${sid}`),
  connection: (sid: number) => api.get<SessionConnectInfo>(`/sessions/${sid}/connection`),
  terminate: (sid: number) => api.del<OkResponse>(`/sessions/${sid}`),
}
