import { api } from './client'
import type { OkResponse, Page } from '@/types/api'

/** 포털 설정 (A-OP-04). 폴링 주기는 C-04로 30초 이하가 요구된다. */
export interface Settings {
  poll_interval_sec: number
  session_timeout_min: number
  smtp_host: string | null
  smtp_port: number | null
  smtp_sender: string | null
  webhook_url: string | null
  updated_at: string | null
}

export interface Notice {
  id: number
  title: string
  body: string | null
  target_cluster_id: number | null
  banner_enabled: boolean
  start_at: string | null
  end_at: string | null
  created_at: string
}

export interface JobTemplate {
  id: number
  name: string
  type: string | null
  version: string | null
  params: Record<string, unknown> | null
  is_public: boolean
  created_at: string
  updated_at: string
}

/** 감사 로그 (A-OP-03, C-05). actor는 서버가 GUID를 이름으로 바꿔 준다. */
export interface AuditLog {
  id: number
  at: string
  actor: string | null
  actor_role: string | null
  action: string
  cluster_id: number | null
  target: string | null
  detail: string | null
  ip: string | null
}

export const opsApi = {
  settings: () => api.get<Settings>('/settings'),
  updateSettings: (payload: Partial<Settings>) => api.put<Settings>('/settings', payload),

  notices: (params?: { cluster_id?: number; banner?: boolean }) => {
    const q = new URLSearchParams()
    if (params?.cluster_id != null) q.set('cluster_id', String(params.cluster_id))
    if (params?.banner) q.set('banner', 'true')
    return api.get<Notice[]>(`/notices${q.toString() ? `?${q}` : ''}`)
  },
  createNotice: (payload: Partial<Notice>) => api.post<Notice>('/notices', payload),
  updateNotice: (id: number, payload: Partial<Notice>) =>
    api.patch<Notice>(`/notices/${id}`, payload),
  removeNotice: (id: number) => api.del<OkResponse>(`/notices/${id}`),

  templates: () => api.get<JobTemplate[]>('/templates'),
  createTemplate: (payload: Partial<JobTemplate>) => api.post<JobTemplate>('/templates', payload),
  removeTemplate: (id: number) => api.del<OkResponse>(`/templates/${id}`),

  auditLogs: (params: {
    actor_username?: string
    action?: string
    page?: number
    size?: number
  }) => {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) if (v) q.set(k, String(v))
    return api.get<Page<AuditLog>>(`/audit-logs?${q}`)
  },
  auditActions: () => api.get<string[]>('/audit-logs/actions'),
}
