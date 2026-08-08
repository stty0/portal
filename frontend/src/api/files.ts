import { api, csrfHeaders, PortalApiError } from './client'

/** 대상 사용자는 서버가 세션에서 정한다 — 클라이언트는 경로만 넘긴다. */
export interface FileEntry {
  name: string
  is_dir: boolean
  size: number
  mtime: number | null
  mode: string
  uid: number | null
  gid: number | null
}

export interface BrowseResponse {
  path: string
  home: string
  /** 탐색이 허용된 최상위 경로들. 이 밖으로는 서버가 403을 낸다. */
  roots: string[]
  entries: FileEntry[]
}

/** 홈만 추린다 — df 원본에는 사용자와 무관한 마운트가 대부분이다. */
export interface StorageTarget {
  label: string
  path: string
  exists: boolean
  mount?: string
  filesystem?: string
  total_bytes?: number
  used_bytes?: number
  avail_bytes?: number
  used_pct?: number | null
}

export interface StorageResponse {
  targets: StorageTarget[]
  quota: { filesystem: string; used_bytes: number; soft_bytes: number; hard_bytes: number }[]
}

/**
 * 업로드·다운로드는 JSON이 아니라 **바이트를 다룬다** — 공용 `api` 헬퍼(JSON 직렬화·
 * 파싱)를 그대로 쓸 수 없어 fetch를 직접 부른다. 오류 형식만 같은 예외로 맞춘다.
 */
async function raw(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: { ...(init.headers ?? {}), ...csrfHeaders() },
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
  return response
}

export const fileApi = {
  browse: (cid: number, path?: string) =>
    api.get<BrowseResponse>(
      `/clusters/${cid}/files${path ? `?path=${encodeURIComponent(path)}` : ''}`,
    ),
  storage: (cid: number) => api.get<StorageResponse>(`/clusters/${cid}/storage`),

  // --- 조작 (U-FM-02·04). 경로는 서버가 정규화해서 돌려준다 ---
  mkdir: (cid: number, path: string) =>
    api.post<{ path: string }>(`/clusters/${cid}/files/directory`, { path }),
  touch: (cid: number, path: string) =>
    api.post<{ path: string }>(`/clusters/${cid}/files/file`, { path }),
  /** 이름 변경과 이동은 같은 연산이다 — 목적지 경로만 다르다. */
  move: (cid: number, path: string, to: string) =>
    api.post<{ path: string }>(`/clusters/${cid}/files/move`, { path, to }),
  remove: (cid: number, path: string, recursive = false) =>
    api.del<{ path: string }>(`/clusters/${cid}/files`, { path, recursive }),

  async upload(cid: number, directory: string, file: File): Promise<{ path: string }> {
    const form = new FormData()
    form.append('path', directory)
    form.append('file', file)
    // Content-Type은 지정하지 않는다 — 브라우저가 multipart 경계를 붙여야 한다.
    const response = await raw(`/clusters/${cid}/files/upload`, { method: 'POST', body: form })
    return response.json()
  },

  async download(cid: number, path: string, name: string): Promise<void> {
    const response = await raw(
      `/clusters/${cid}/files/download?path=${encodeURIComponent(path)}`,
      { method: 'GET' },
    )
    // 링크를 새 탭으로 여는 방식은 Authorization 헤더를 못 붙인다 — 받아서 저장한다.
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = name
    link.click()
    URL.revokeObjectURL(url)
  },
}
