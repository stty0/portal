/** 백엔드 스키마 대응 타입 (backend/app/schemas/*). */

export interface ApiError {
  code: string
  message: string
  detail?: unknown
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface OkResponse {
  ok: boolean
  message?: string | null
}

// --- Auth ---------------------------------------------------------
export interface SetupStatus {
  bootstrap_required: boolean
}

export interface SetupRequest {
  setup_token: string
  ldaps_url: string
  base_dn: string
  bind_account: string
  bind_password: string
  allowed_group?: string | null
  id_attribute?: string
  seed_admin_username: string
}

export interface AdCandidate {
  object_guid: string
  username: string
  display_name: string | null
  email: string | null
}

export interface SetupProbeResponse {
  ok: boolean
  users: AdCandidate[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface Me {
  username: string
  display_name: string | null
  role: string | null
  permissions: string[]
  default_cluster_id: number | null
}

// --- Users / AD ---------------------------------------------------
export interface User {
  ad_object_guid: string
  username: string
  display_name: string | null
  email: string | null
  is_active: boolean
  default_cluster_id: number | null
  last_login_at: string | null
  role: string | null
}

export interface AdConnection {
  ldaps_url: string | null
  base_dn: string | null
  bind_account: string | null
  allowed_group: string | null
  id_attribute: string | null
  sync_interval: string | null
  last_sync_at: string | null
  last_sync_result: string | null
  bind_secret_configured: boolean
  bootstrap_completed: boolean
}

export interface AdSyncResult {
  ok: boolean
  created: number
  updated: number
  deactivated: number
  message: string
}

// --- Clusters -----------------------------------------------------
export interface ClusterSummary {
  id: number
  name: string
  description: string | null
  is_default: boolean
  is_active: boolean
}

export interface Cluster extends ClusterSummary {
  slurmrestd_url: string | null
  api_version: string | null
  auth_method: string | null
  login_node: string | null
  ssh_port: number | null
  ssh_account: string | null
  group_path_tpl: string | null
  scratch_path_tpl: string | null
  created_at?: string | null
  last_health_at?: string | null
  last_health_ok?: boolean | null
  /** 자격증명의 참조 정보만 — 값은 응답에 없다. */
  credentials?: CredentialOut[]
}

export interface ClusterCreate {
  name: string
  description?: string | null
  slurmrestd_url?: string | null
  api_version?: string | null
  auth_method?: string | null
  login_node?: string | null
  ssh_port?: number | null
  ssh_account?: string | null
  group_path_tpl?: string | null
  scratch_path_tpl?: string | null
  is_default?: boolean
}

export interface CredentialOut {
  id: number
  kind: string
  expires_at: string | null
  created_at: string
}

export interface RestTestResult {
  ok: boolean
  cluster_name?: string | null
  api_version?: string | null
}

// --- Jobs ---------------------------------------------------------
/** slurmrestd 응답은 버전마다 형태가 달라 백엔드가 그대로 흘려보낸다. */
export type SlurmJob = Record<string, unknown> & {
  job_id?: number | string
  name?: string
  user_name?: string
  job_state?: string | string[]
  partition?: string
  account?: string
  qos?: string
  nodes?: string
  script?: string
}

export interface JobListResponse {
  items: SlurmJob[]
  total: number
  /** 이력 출처 — slurmdbd 미연결 시 'slurmctld'(최근 완료 Job만). */
  source?: string | null
}

export interface JobSubmitRequest {
  name: string
  /** form이면 폼 값이 #SBATCH 지시자로 생성되고, script면 본문을 그대로 쓴다. */
  mode?: 'form' | 'script' | 'template'
  partition?: string | null
  account?: string | null
  qos?: string | null
  nodes?: number | null
  cpus_per_task?: number | null
  gpus?: number | null
  memory_gb?: number | null
  walltime?: string | null
  work_dir?: string | null
  environment?: Record<string, string> | null
  script?: string | null
  template_id?: number | null
  template_params?: Record<string, unknown> | null
}

export interface JobSubmitResponse {
  job_id: string | null
  raw?: unknown
}
