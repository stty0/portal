/**
 * slurmrestd 자원 응답 어댑터 (노드·파티션·예약).
 *
 * v0.0.41은 숫자를 `{set, infinite, number}` 래퍼로 감싸 보낸다.
 * 화면에서 매번 풀면 실수가 나므로 여기 한 곳에서만 푼다.
 * Job 어댑터(utils/job.ts)와 같은 태도 — 필드가 없거나 형태가 달라도 화면이 깨지지 않아야 한다.
 */

export type SlurmRecord = Record<string, unknown>

/** `{set,infinite,number}` 또는 평범한 숫자를 숫자로. 무한/미설정은 null. */
export function num(value: unknown): number | null {
  if (typeof value === 'number') return value
  if (value && typeof value === 'object') {
    const w = value as { set?: boolean; infinite?: boolean; number?: number }
    if (w.infinite || w.set === false) return null
    if (typeof w.number === 'number') return w.number
  }
  return null
}

/** 무한/미설정을 기호로 표시한다 — 0과 구분되어야 한다. */
export function numText(value: unknown, unit = ''): string {
  const n = num(value)
  return n === null ? '∞' : `${n}${unit}`
}

export function text(row: SlurmRecord, key: string, fallback = '—'): string {
  const v = row[key]
  if (v === null || v === undefined || v === '') return fallback
  if (Array.isArray(v)) return v.length ? v.join(', ') : fallback
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** 상태는 배열로 온다: ["IDLE"], ["ALLOCATED","DRAIN"] 처럼 복합일 수 있다. */
export function states(row: SlurmRecord, key = 'state'): string[] {
  const raw = row[key]
  if (Array.isArray(raw)) return raw.map(String)
  return raw ? [String(raw)] : []
}

/** 노드/파티션 상태 → Badge 색. 알 수 없으면 회색으로 떨어진다. */
export function resourceTone(state: string): string {
  const s = state.toUpperCase()
  if (s.startsWith('IDLE') || s === 'UP') return 'idle'
  if (s.startsWith('ALLOC')) return 'alloc'
  if (s.startsWith('MIX')) return 'mix'
  if (s.startsWith('DRAIN') || s.startsWith('DRNG')) return 'drain'
  if (s.startsWith('DOWN') || s.startsWith('FAIL') || s === 'INACTIVE') return 'down'
  return 'idle'
}

export function mib(value: unknown): string {
  const n = num(value)
  if (n === null) return '—'
  return n >= 1024 ? `${(n / 1024).toFixed(1)} GB` : `${n} MB`
}
