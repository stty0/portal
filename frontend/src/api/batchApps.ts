import { api } from './client'
import type { JobSubmitRequest, JobSubmitResponse } from '@/types/api'

export interface AppParam {
  key: string
  label: string
  /** text · number · path(홈 하위 절대 경로) · select */
  type: string
  required: boolean
  default: string | null
  hint: string
  options: string[]
}

export interface BatchApp {
  id: string
  name: string
  description: string
  fid: string
  needs_gpu: boolean
  /** **실행 방식**(기동 커맨드·파라미터)이 확정됐는가. 코드가 답한다. */
  ready: boolean
  /**
   * 이 **클러스터에** 이미지 파일이 있는가. 클러스터가 답하고, SIF를 디렉터리에 넣으면
   * 코드 배포 없이 참이 된다.
   */
  installed: boolean
  params: AppParam[]
  /** 이 사용자가 쓸 수 있는가. 세 번째 잠금 — 계정 배정에서 빠진 경우다. */
  allowed: boolean
  /** 이 앱에 배정된 계정. 비어 있으면 전원 허용이다. */
  accounts: string[]
}

export interface BatchAppSubmit extends JobSubmitRequest {
  params: Record<string, string>
}

export const batchAppApi = {
  // 인터랙티브 앱과 같은 이유로 클러스터에 매인다 — 계정 배정이 클러스터별이다.
  list: (cid: number) => api.get<BatchApp[]>(`/clusters/${cid}/batch-apps`),
  submit: (cid: number, appId: string, payload: BatchAppSubmit) =>
    api.post<JobSubmitResponse>(`/clusters/${cid}/batch-apps/${appId}/jobs`, payload),
}
