import { api } from './client'

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
  shortcuts: { label: string; path: string; exists: boolean }[]
  entries: FileEntry[]
}

/** 홈·스크래치·그룹만 추린다. 없는 경로는 exists=false 로 온다. */
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

export const fileApi = {
  browse: (cid: number, path?: string) =>
    api.get<BrowseResponse>(
      `/clusters/${cid}/files${path ? `?path=${encodeURIComponent(path)}` : ''}`,
    ),
  storage: (cid: number) => api.get<StorageResponse>(`/clusters/${cid}/storage`),
}
