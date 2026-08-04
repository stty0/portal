import type { SlurmJob } from '@/types/api'

/**
 * slurmrestd 응답 어댑터.
 *
 * v0.0.41 응답 스키마를 실물로 확정하지 못해 백엔드도 방어적으로 파싱한다
 * (backend/app/services/job.py). 프론트도 같은 태도를 유지한다 — 필드가 없거나
 * 형태가 달라도 화면이 깨지지 않아야 한다.
 */

export function jobId(job: SlurmJob): string {
  return String(job.job_id ?? '')
}

export function jobState(job: SlurmJob): string {
  const raw = job.job_state ?? (job as Record<string, unknown>).state
  if (Array.isArray(raw)) return String(raw[0] ?? '')
  if (raw && typeof raw === 'object') {
    return String((raw as Record<string, unknown>).current ?? '')
  }
  return String(raw ?? '')
}

export function jobField(job: SlurmJob, key: string, fallback = '—'): string {
  const value = (job as Record<string, unknown>)[key]
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** 상태 배지 색을 위한 정규화. */
export function stateTone(state: string): string {
  const s = state.toUpperCase()
  if (s.startsWith('RUN')) return 'running'
  if (s.startsWith('PEND')) return 'pending'
  if (s.startsWith('COMPL')) return 'completed'
  if (s.startsWith('FAIL') || s.startsWith('NODE_FAIL') || s.startsWith('TIMEOUT')) return 'failed'
  if (s.startsWith('CANCEL')) return 'cancelled'
  return 'idle'
}
