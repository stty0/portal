import { api } from './client'
import type {
  Cluster,
  ClusterCreate,
  ClusterSummary,
  CredentialOut,
  OkResponse,
  RestTestResult,
} from '@/types/api'
import type { SlurmRecord } from '@/utils/slurm'

/** QOS 정책 (A-US-03). 제한값 없음 = 무제한. */
export interface SlurmQos {
  name: string
  description: string | null
  priority: number | null
  usage_factor: number | null
  flags: string[]
  max_wall_minutes: number | null
  max_jobs_per_user: number | null
  max_submit_per_user: number | null
}

/** Slurm 계정과 소속 사용자 (A-US-02). */
export interface SlurmAccount {
  name: string
  description: string | null
  organization: string | null
  coordinators: unknown[]
  /** 계정 단위 허용 QOS. 사용자 행의 qos와 별개다. */
  qos: string[]
  users: {
    user: string
    cluster: string
    partition: string | null
    qos: string[]
    is_default: boolean
    shares_raw: number | null
  }[]
}

export const clusterApi = {
  /** includeInactive는 관리 화면 전용 — 사용자 선택 목록에는 활성 클러스터만 내려온다. */
  list: (includeInactive = false) =>
    api.get<ClusterSummary[]>(`/clusters${includeInactive ? '?include_inactive=true' : ''}`),
  create: (payload: ClusterCreate) => api.post<Cluster>('/clusters', payload),
  get: (cid: number) => api.get<Cluster>(`/clusters/${cid}`),
  update: (cid: number, payload: Partial<ClusterCreate>) =>
    api.patch<Cluster>(`/clusters/${cid}`, payload),
  remove: (cid: number) => api.del<OkResponse>(`/clusters/${cid}`),
  purge: (cid: number) => api.del<OkResponse>(`/clusters/${cid}/purge`),
  putCredential: (cid: number, kind: 'SLURM_JWT' | 'SSH_KEY', value: string) =>
    api.put<CredentialOut>(`/clusters/${cid}/credentials`, { kind, value }),
  testRest: (cid: number) => api.post<RestTestResult>(`/clusters/${cid}/test-rest`),
  /** slurmrestd 원본을 그대로 받는다 — 필드가 버전마다 달라 타입을 고정하지 않는다. */
  nodes: (cid: number) => api.get<SlurmRecord[]>(`/clusters/${cid}/nodes`),
  partitions: (cid: number) => api.get<SlurmRecord[]>(`/clusters/${cid}/partitions`),
  reservations: (cid: number) => api.get<SlurmRecord[]>(`/clusters/${cid}/reservations`),
  accounts: (cid: number) => api.get<SlurmAccount[]>(`/clusters/${cid}/accounts`),
  createAccount: (cid: number, payload: { name: string; description?: string; organization?: string }) =>
    api.post<{ ok: boolean }>(`/clusters/${cid}/accounts`, payload),
  deleteAccount: (cid: number, name: string) =>
    api.del<{ ok: boolean }>(`/clusters/${cid}/accounts/${encodeURIComponent(name)}`),
  addAccountUser: (cid: number, name: string, username: string) =>
    api.post<{ ok: boolean }>(`/clusters/${cid}/accounts/${encodeURIComponent(name)}/users`, {
      username,
    }),
  qos: (cid: number) => api.get<SlurmQos[]>(`/clusters/${cid}/qos`),
  /** QOS 지정은 **덮어쓰기**다 — 현재 목록에 더하거나 뺀 전체 집합을 보낸다. */
  setAccountQos: (cid: number, account: string, qos: string[]) =>
    api.put<{ ok: boolean }>(`/clusters/${cid}/accounts/${encodeURIComponent(account)}/qos`, {
      qos,
    }),
  setUserQos: (cid: number, account: string, username: string, qos: string[]) =>
    api.put<{ ok: boolean }>(
      `/clusters/${cid}/accounts/${encodeURIComponent(account)}/users/${encodeURIComponent(username)}/qos`,
      { qos },
    ),
  createQos: (
    cid: number,
    payload: {
      name: string
      description?: string
      priority?: number | null
      max_wall_minutes?: number | null
      max_jobs_per_user?: number | null
    },
  ) => api.post<{ ok: boolean }>(`/clusters/${cid}/qos`, payload),
  deleteQos: (cid: number, name: string) =>
    api.del<{ ok: boolean }>(`/clusters/${cid}/qos/${encodeURIComponent(name)}`),
  removeAccountUser: (cid: number, name: string, username: string) =>
    api.del<{ ok: boolean }>(
      `/clusters/${cid}/accounts/${encodeURIComponent(name)}/users/${encodeURIComponent(username)}`,
    ),
}
