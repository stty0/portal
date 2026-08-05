import { api } from './client'
import type { JobListResponse, JobSubmitRequest, JobSubmitResponse, SlurmJob } from '@/types/api'

export interface JobOptions {
  partitions: string[]
  accounts: string[]
  qos: string[]
}

export const jobApi = {
  /** 제출 폼 선택지. 조회 실패한 항목은 빈 배열로 온다(slurmdbd만 끊긴 환경 등). */
  options: (cid: number) => api.get<JobOptions>(`/clusters/${cid}/job-options`),
  list: (cid: number, filters: Record<string, string | undefined> = {}) =>
    api.get<JobListResponse>(`/clusters/${cid}/jobs`, filters),
  history: (cid: number, filters: Record<string, string | undefined> = {}) =>
    api.get<JobListResponse>(`/clusters/${cid}/jobs/history`, filters),
  get: (cid: number, jobId: string) => api.get<SlurmJob>(`/clusters/${cid}/jobs/${jobId}`),
  submit: (cid: number, payload: JobSubmitRequest) =>
    api.post<JobSubmitResponse>(`/clusters/${cid}/jobs`, payload),
  previewScript: (cid: number, payload: JobSubmitRequest) =>
    api.post<{ script: string }>(`/clusters/${cid}/jobs/preview-script`, payload),
  cancel: (cid: number, jobId: string) => api.del(`/clusters/${cid}/jobs/${jobId}`),
  resubmit: (cid: number, jobId: string, overrides: Record<string, unknown> = {}) =>
    api.post<JobSubmitResponse>(`/clusters/${cid}/jobs/${jobId}/resubmit`, overrides),
  control: (cid: number, jobId: string, action: 'hold' | 'release' | 'priority', priority?: number) =>
    api.patch(`/clusters/${cid}/jobs/${jobId}`, { action, priority }),
}
