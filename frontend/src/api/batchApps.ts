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
  /** 준비 전 앱도 목록에 온다 — 고를 수만 없다. */
  ready: boolean
  params: AppParam[]
}

export interface BatchAppSubmit extends JobSubmitRequest {
  params: Record<string, string>
}

export const batchAppApi = {
  list: () => api.get<BatchApp[]>('/batch-apps'),
  submit: (cid: number, appId: string, payload: BatchAppSubmit) =>
    api.post<JobSubmitResponse>(`/clusters/${cid}/batch-apps/${appId}/jobs`, payload),
}
