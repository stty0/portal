import { api, csrfHeaders, PortalApiError } from './client'
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
  banner_enabled: boolean
  start_at: string | null
  end_at: string | null
  created_at: string
}
/**
 * 앱 카탈로그 (A-OP-02). 앱의 **정보**만 담는다 — 실행 방식(기동 스크립트·transport·
 * 파라미터 스키마)은 백엔드 코드 카탈로그가 정본이고 여기로 오지 않는다.
 * `kind` + `app_id`가 코드 카탈로그로 가는 연결 키다.
 */
export interface AppCatalog {
  /** 등록 행의 PK. **null이면 아직 등록되지 않은 코드 앱**(수정이 아니라 등록 대상). */
  id: number | null
  /** 코드 카탈로그에 있는 앱인가. false = 관리자가 미리 등록해 둔 도입 예정 앱. */
  in_code: boolean
  kind: 'interactive' | 'batch'
  app_id: string
  name: string
  vendor: string | null
  version: string | null
  /** 컨테이너 이미지 **파일명**. 파일은 클러스터의 공유 이미지 디렉터리에 있다. */
  image_file: string | null
  /** 아이콘 **파일명**. 등록 폼이 고르는 값이며 서버의 아이콘 디렉터리에 있는 파일이다. */
  icon_file: string | null
  /** 서버가 파일명으로 만든 주소. 화면은 이걸 그대로 <img src>에 넣는다. */
  icon_url: string | null
  description: string | null
  updated_at: string | null
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

  /** 공지는 **포털 전체 대상**이다 — 클러스터로 거르지 않는다. */
  notices: (params?: { banner?: boolean }) =>
    api.get<Notice[]>(`/notices${params?.banner ? '?banner=true' : ''}`),
  createNotice: (payload: Partial<Notice>) => api.post<Notice>('/notices', payload),
  updateNotice: (id: number, payload: Partial<Notice>) =>
    api.patch<Notice>(`/notices/${id}`, payload),
  removeNotice: (id: number) => api.del<OkResponse>(`/notices/${id}`),

  /** 앱 카탈로그 (A-OP-02). 읽기는 인증 사용자, 쓰기는 ADMIN. */
  apps: () => api.get<AppCatalog[]>('/apps'),
  createApp: (payload: Partial<AppCatalog>) => api.post<AppCatalog>('/apps', payload),
  updateApp: (id: number, payload: Partial<AppCatalog>) =>
    api.patch<AppCatalog>(`/apps/${id}`, payload),
  removeApp: (id: number) => api.del<OkResponse>(`/apps/${id}`),
  /** 아이콘 디렉터리에 놓인 파일명 목록 — 등록 폼의 선택지. */
  appIcons: () => api.get<string[]>('/app-icons'),
  /** 컨테이너 이미지 디렉터리의 파일명 목록. */

  /** 아이콘 업로드. 응답은 갱신된 파일명 목록이며, **이름은 서버가 정한다**. */
  async uploadAppIcon(file: File): Promise<string[]> {
    const form = new FormData()
    form.append('file', file)
    // Content-Type은 지정하지 않는다 — 브라우저가 multipart 경계를 붙여야 한다.
    const response = await fetch('/api/v1/app-icons', {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      headers: { ...csrfHeaders() },
    })
    if (!response.ok) {
      let body: Record<string, unknown> = {}
      try {
        body = await response.json()
      } catch {
        /* 본문이 JSON이 아니면 상태만 남긴다 */
      }
      throw new PortalApiError(response.status, body)
    }
    return response.json()
  },


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
