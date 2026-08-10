import { api } from './client'
import type {
  Cluster,
  ClusterCreate,
  ClusterSummary,
  CredentialOut,
  OkResponse,
  ImageDirCheck,
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

/**
 * 앱 하나에 배정된 계정 (A-US-02). **`accounts`가 비면 전원 허용**이다 —
 * 배정하지 않은 앱은 지금까지처럼 누구나 쓴다.
 */
export interface AppAccess {
  /** interactive · batch — 두 카탈로그의 앱 id가 겹칠 수 있어 함께 키가 된다. */
  kind: string
  app_id: string
  name: string
  accounts: string[]
}

/** 클러스터 부하 요약 (A-DB-02). slurmctld 노드 상태에서 집계된다. */
export interface ClusterMetrics {
  nodes: number
  states: { state: string; count: number }[]
  cpus: number
  alloc_cpus: number
  cpu_pct: number | null
  memory_mb: number
  alloc_memory_mb: number
  memory_pct: number | null
  load_per_cpu: number | null
}

/** 최근 이벤트 (A-DB-04) = 이 클러스터 대상 감사 로그. */
export interface ClusterEvent {
  at: string
  actor: string | null
  actor_role: string | null
  action: string
  target: string | null
  detail: string | null
}

export interface ReservationCreate {
  name: string
  /** epoch 초. 화면은 로컬 시각 입력을 변환해 보낸다. */
  start_time: number
  duration_minutes: number
  node_list?: string | null
  node_count?: number | null
  partition?: string | null
  users?: string | null
  accounts?: string | null
  flags?: string[]
  comment?: string | null
}

export const clusterApi = {
  /** 등록 폼의 API 버전 선택지. 목록은 서버가 단일 출처다. */
  apiVersions: () => api.get<string[]>('/cluster-api-versions'),
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
  /**
   * A-ND-04 예약 생성. 숫자는 서버가 slurmrestd의 `{set,infinite,number}` 래퍼로 감싼다.
   * `node_list`나 `node_count` 중 하나는 필수다(없으면 클러스터 전체를 잡을 수 있다).
   */
  createReservation: (cid: number, body: ReservationCreate) =>
    api.post<{ ok: boolean; name: string }>(`/clusters/${cid}/reservations`, body),
  deleteReservation: (cid: number, name: string) =>
    api.del<{ ok: boolean; name: string }>(
      `/clusters/${cid}/reservations/${encodeURIComponent(name)}`,
    ),
  /** A-ND-01 노드 상태 제어. drain·down은 사유가 필수다(서버가 강제). */
  setNodeState: (cid: number, name: string, state: string, reason?: string) =>
    api.post<{ ok: boolean; node: string; state: string }>(
      `/clusters/${cid}/nodes/${encodeURIComponent(name)}/state`,
      { state, reason: reason || null },
    ),
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
  /** 이 클러스터에 실제로 있는 이미지 파일. 경로가 클러스터마다 갈려 포털이 답할 수 없다. */
  appImages: (cid: number) => api.get<string[]>(`/clusters/${cid}/app-images`),
  /** 등록 직후 진단. **없어도 200**이다 — 포털은 디렉터리를 만들지 않고 알리기만 한다. */
  imageDir: (cid: number) => api.get<ImageDirCheck>(`/clusters/${cid}/image-dir`),
  /** OCI 참조 → SIF를 **Slurm 잡으로** 만든다. 결과는 요청자 홈 아래에 떨어진다. */
  buildAppImage: (cid: number, kind: string, appId: string) =>
    api.post<{ job_id: string }>(`/clusters/${cid}/app-images/${kind}/${appId}/build`),
  /** 빌드된 SIF를 이미지 디렉터리로 옮긴다 — 포털이 유일하게 권한을 올리는 지점. */
  installAppImage: (cid: number, kind: string, appId: string) =>
    api.post<OkResponse>(`/clusters/${cid}/app-images/${kind}/${appId}/install`),
  appAccess: (cid: number) => api.get<AppAccess[]>(`/clusters/${cid}/app-access`),
  /** 계정 배정도 QOS와 같은 **덮어쓰기**다. 빈 배열을 보내면 그 앱이 다시 전원에게 열린다. */
  setAppAccess: (cid: number, kind: string, appId: string, accounts: string[]) =>
    api.put<AppAccess>(`/clusters/${cid}/app-access/${kind}/${appId}`, { accounts }),
  metrics: (cid: number) => api.get<ClusterMetrics>(`/clusters/${cid}/metrics`),
  events: (cid: number, limit = 20) =>
    api.get<ClusterEvent[]>(`/clusters/${cid}/events?limit=${limit}`),
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
