import { api } from './client'

/** 통계·리포트 (A-RP-01·02·03). 모두 slurmdbd 완료 Job에서 파생된다. */
export interface UsageReport {
  start: string
  end: string
  total_jobs: number
  total_cpu_hours: number
  by_user: UsageRow[]
  by_account: UsageRow[]
  by_partition: UsageRow[]
}

export interface UsageRow {
  key: string
  jobs: number
  failed: number
  cpu_hours: number
}

export interface UtilizationReport {
  start: string
  end: string
  total_cpus: number
  daily_capacity_cpu_hours: number
  daily: { date: string; cpu_hours: number; pct: number | null }[]
}

export interface WaitTimeReport {
  start: string
  end: string
  samples: number
  avg_seconds: number | null
  median_seconds: number | null
  max_seconds: number | null
  histogram: { label: string; count: number }[]
  by_partition: {
    partition: string
    samples: number
    avg_seconds: number
    max_seconds: number
  }[]
}

export const reportApi = {
  usage: (cid: number, days = 30) =>
    api.get<UsageReport>(`/clusters/${cid}/reports/usage?days=${days}`),
  utilization: (cid: number, days = 30) =>
    api.get<UtilizationReport>(`/clusters/${cid}/reports/utilization?days=${days}`),
  waitTime: (cid: number, days = 30) =>
    api.get<WaitTimeReport>(`/clusters/${cid}/reports/wait-time?days=${days}`),
}
