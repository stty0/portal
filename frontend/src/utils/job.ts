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

/**
 * 소유자 이름. slurmctld는 `user_name`, slurmdbd(이력)는 `user`로 준다 — 실측.
 * 화면에서 두 출처를 같은 표에 섞어 쓰므로 여기서 흡수한다.
 */
export function jobOwner(job: SlurmJob): string {
  const raw = job.user_name ?? (job as Record<string, unknown>).user
  return raw ? String(raw) : '—'
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


/**
 * 종료된 Job — 제어(Hold/Release/취소)가 의미 없는 상태.
 * 이력 탭은 대부분 여기에 해당한다.
 */
const TERMINAL_STATES = [
  'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL', 'PREEMPTED',
  'BOOT_FAIL', 'DEADLINE', 'OUT_OF_MEMORY', 'REVOKED', 'SPECIAL_EXIT',
]

export function isTerminal(job: SlurmJob): boolean {
  const state = jobState(job).toUpperCase()
  return TERMINAL_STATES.some((t) => state.startsWith(t))
}

/** 취소는 아직 끝나지 않은 Job에만 가능하다. */
export function canCancel(job: SlurmJob): boolean {
  return !isTerminal(job)
}

/** Hold/Release는 대기 중인 Job에만 의미가 있다 — 실행이 시작되면 되돌릴 수 없다. */
export function canHold(job: SlurmJob): boolean {
  return jobState(job).toUpperCase().startsWith('PEND')
}


/**
 * 대기 사유 (`state_reason`).
 *
 * **끝났거나 사유가 없으면 문자열 `"None"`으로 온다**(실측 2026-08-08) — 빈 값이 아니라
 * 이 네 글자다. 그대로 화면에 쓰면 "None"이라고 적힌 칸이 생긴다.
 */
export function waitReason(job: SlurmJob): string {
  const raw = String((job as Record<string, unknown>).state_reason ?? '').trim()
  return raw === '' || raw === 'None' ? '' : raw
}

/** 의존성 표기. 대기 중이면 `afterok:69(unfulfilled)`처럼 상태가 붙어 온다(실측). */
export function jobDependency(job: SlurmJob): string {
  return String((job as Record<string, unknown>).dependency ?? '').trim()
}

/**
 * **영원히 시작되지 않는다.** 선행 Job이 실패·취소돼 `afterok` 조건이 깨진 상태다
 * (실측: `state_reason=DependencyNeverSatisfied`, `dependency=afterok:69(failed)`).
 *
 * Slurm은 이 Job을 자동으로 치우지 않는다 — 사람이 취소해야 큐에서 사라진다.
 * 그래서 다른 PENDING과 **같아 보이면 안 된다**.
 */
export function isBlockedForever(job: SlurmJob): boolean {
  return waitReason(job).toLowerCase().includes('dependencyneversatisfied')
}

/** 대기 사유를 사람 말로. 모르는 값은 원문 그대로 둔다(추측해서 바꾸지 않는다). */
const REASON_TEXT: Record<string, string> = {
  Dependency: '앞 Job을 기다리는 중',
  DependencyNeverSatisfied: '앞 Job이 실패해 영원히 시작되지 않습니다',
  Resources: '자원이 나기를 기다리는 중',
  Priority: '우선순위가 높은 Job이 먼저',
  PartitionNodeLimit: '요청한 노드 수가 파티션 한도를 넘습니다',
  PartitionTimeLimit: '요청한 실행 시간이 파티션 한도를 넘습니다',
  QOSMaxJobsPerUserLimit: 'QOS의 동시 실행 Job 수 한도에 걸렸습니다',
  JobHeldUser: '사용자가 보류했습니다',
  JobHeldAdmin: '관리자가 보류했습니다',
  BeginTime: '시작 예정 시각을 기다리는 중',
  ReqNodeNotAvail: '요청한 노드를 쓸 수 없습니다',
}

export function waitReasonText(job: SlurmJob): string {
  const reason = waitReason(job)
  return reason ? (REASON_TEXT[reason] ?? reason) : ''
}


/** 의존성 한 항목 — `afterok:73(failed)` 또는 `afterany:11:12` 를 푼 결과. */
export interface DependencyTerm {
  /** `afterok`·`afterany`·`singleton` 등. */
  type: string
  /** 앞 Job들. `singleton`처럼 대상이 없는 종류는 빈 배열이다. */
  jobs: { id: string; note: string }[]
}

/** 종류별 한 줄 설명. 모르는 종류는 원문을 그대로 쓴다. */
const DEPENDENCY_TEXT: Record<string, string> = {
  afterok: '앞 Job이 성공해야 시작',
  afternotok: '앞 Job이 실패해야 시작',
  afterany: '앞 Job이 끝나면 시작(성공·실패 무관)',
  after: '앞 Job이 시작되면 시작',
  aftercorr: '배열 대 배열 — 같은 인덱스끼리',
  afterburstbuffer: '앞 Job의 버스트 버퍼 단계가 끝나면 시작',
  singleton: '같은 이름의 내 Job이 하나만 돌게',
}

/** 앞 Job의 현재 처지. Slurm이 괄호로 붙여 준다(실측: unfulfilled·failed). */
const NOTE_TEXT: Record<string, string> = {
  unfulfilled: '대기',
  failed: '실패',
  satisfied: '충족',
}

export function dependencyText(type: string): string {
  return DEPENDENCY_TEXT[type.toLowerCase()] ?? type
}

export function dependencyNoteText(note: string): string {
  return NOTE_TEXT[note.toLowerCase()] ?? note
}

/**
 * 의존성 문자열 → 항목 목록.
 *
 * Slurm 표기를 그대로 받아 푼다 — `,`는 AND, `?`는 OR이고, 한 항목에 Job이 여럿 붙을 수
 * 있다(`afterany:11:12`). 대기 중이면 `afterok:73(unfulfilled)`처럼 처지가 괄호로 붙는다.
 *
 * **모르는 표기는 버리지 않는다** — 종류만 담고 Job은 비워 둔다. 화면이 원문을 잃으면
 * 사용자는 무엇에 걸려 있는지 알 방법이 없어진다.
 */
export function parseDependency(raw: string): DependencyTerm[] {
  const terms: DependencyTerm[] = []
  for (const chunk of raw.split(/[,?]/)) {
    const text = chunk.trim()
    if (!text) continue
    const [type, ...rest] = text.split(':')
    const jobs: { id: string; note: string }[] = []
    for (const piece of rest) {
      const found = /^(\d+)(?:\(([^)]*)\))?/.exec(piece.trim())
      if (found) jobs.push({ id: found[1], note: found[2] ?? '' })
    }
    terms.push({ type: type.trim(), jobs })
  }
  return terms
}


/**
 * 시간 필드 어댑터 — **두 출처의 형태가 완전히 다르다**(실측 2026-08-08).
 *
 *   slurmctld(진행 중): 평평한 키 + `{set,infinite,number}` 래퍼
 *                       `start_time` · `end_time` · `submit_time`, elapsed 없음
 *   slurmdbd(이력):     중첩 `time` 객체 + 맨 정수
 *                       `time.start` · `time.end` · `time.elapsed`
 *
 * 이력 탭은 slurmdbd가 끊기면 slurmctld로 대체되므로(`source`), **한 탭에 두 형태가
 * 섞여 들어온다.** 그래서 화면이 아니라 여기서 흡수한다.
 *
 * `0`은 1970년이 아니라 **"아직 없음"** 이다 — 대기 중 Job의 start, 실행 중 Job의 end이 0으로 온다.
 */
function epoch(value: unknown): number | null {
  const n =
    typeof value === 'number'
      ? value
      : value && typeof value === 'object'
        ? ((value as { number?: number }).number ?? null)
        : null
  return n !== null && n > 0 ? n : null
}

function timeNode(job: SlurmJob): Record<string, unknown> | null {
  const raw = (job as Record<string, unknown>).time
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : null
}

export function jobStartedAt(job: SlurmJob): number | null {
  const t = timeNode(job)
  return epoch(t?.start) ?? epoch((job as Record<string, unknown>).start_time)
}

/**
 * **실제로 끝난 시각만.** 아직 도는 Job의 slurmctld `end_time`은 *예상* 종료(시작+제한시간)라
 * 그대로 쓰면 끝나지도 않은 Job에 종료 시각이 찍힌다.
 */
export function jobEndedAt(job: SlurmJob): number | null {
  const t = timeNode(job)
  const fromDb = epoch(t?.end)
  if (fromDb !== null) return fromDb
  return isTerminal(job) ? epoch((job as Record<string, unknown>).end_time) : null
}

/**
 * 수행 시간(초). 아직 도는 Job은 **지금까지** 돈 시간이다.
 * `nowSeconds`를 밖에서 받는 이유: 화면이 1초마다 새로 그릴 수 있게 하려면 시계가 반응형이어야 한다.
 */
export function jobElapsedSeconds(job: SlurmJob, nowSeconds: number): number | null {
  const reported = timeNode(job)?.elapsed
  // 0초 실행도 사실이므로 `truthy` 검사로 걸러내지 않는다.
  if (typeof reported === 'number' && reported >= 0) return reported
  const start = jobStartedAt(job)
  if (start === null) return null
  return Math.max(0, (jobEndedAt(job) ?? nowSeconds) - start)
}

/** 초 → `HH:MM:SS`, 하루를 넘으면 `N일 HH:MM:SS`. */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—'
  const days = Math.floor(seconds / 86400)
  const rest = seconds % 86400
  const hh = String(Math.floor(rest / 3600)).padStart(2, '0')
  const mm = String(Math.floor((rest % 3600) / 60)).padStart(2, '0')
  const ss = String(rest % 60).padStart(2, '0')
  return `${days ? `${days}일 ` : ''}${hh}:${mm}:${ss}`
}

const pad = (n: number) => String(n).padStart(2, '0')

/** epoch → `MM-DD HH:MM:SS`(현지). 연도는 title에만 둔다 — 표 칸이 좁다. */
export function formatTimestamp(seconds: number | null): string {
  if (seconds === null) return '—'
  const d = new Date(seconds * 1000)
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatTimestampFull(seconds: number | null): string {
  if (seconds === null) return ''
  const d = new Date(seconds * 1000)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
