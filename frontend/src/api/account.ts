import { api } from './client'

/** 내 사용량 (U-AC-01). 값은 slurmdbd 회계 Job에서 계산된다. */
export interface MyUsage {
  start: string
  end: string
  total_jobs: number
  total_cpu_hours: number
  total_gpu_hours: number
  failed_jobs: number
  daily: { date: string; jobs: number; cpu_hours: number; gpu_hours: number; failed: number }[]
  by_partition: UsageRow[]
  by_account: UsageRow[]
}

export interface UsageRow {
  label: string
  jobs: number
  cpu_hours: number
  gpu_hours: number
  failed: number
}

/** Fairshare / QOS 한도 (U-AC-02). 한도가 null이면 **무제한**이다. */
export interface MyFairshare {
  username: string
  associations: {
    account: string | null
    partition: string | null
    is_default: boolean
    shares_raw: number | null
    qos: string[]
  }[]
  qos: {
    name: string
    description: string | null
    priority: number | null
    usage_factor: number | null
    max_wall_minutes: number | null
    max_jobs_per_user: number | null
    max_submit_per_user: number | null
  }[]
  /** sshare 결과. 빈 목록이면 클러스터가 이 정보를 주지 않는 것이다. */
  shares: {
    account: string
    user: string | null
    raw_shares: number | null
    norm_shares: number | null
    raw_usage: number | null
    effective_usage: number | null
    fairshare: number | null
  }[]
}

export const accountApi = {
  usage: (cid: number, days = 30) => api.get<MyUsage>(`/clusters/${cid}/me/usage?days=${days}`),
  fairshare: (cid: number) => api.get<MyFairshare>(`/clusters/${cid}/me/fairshare`),
}
