import type { ApiError } from '@/types/api'

const BASE = '/api/v1'
/**
 * 자격증명은 **HttpOnly 쿠키**가 나른다 — JS가 읽을 수 없으므로 XSS로 토큰을 빼갈 수
 * 없다. 대신 브라우저가 자동으로 붙이므로 CSRF를 막아야 한다: 서버가 심어 준
 * `portal_csrf`(읽기 가능)를 헤더로 되돌려 보낸다. 다른 오리진은 이 쿠키를 못 읽는다.
 */
const CSRF_COOKIE = 'portal_csrf'
const CSRF_HEADER = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

/** 백엔드 오류 형식({code,message,detail})을 그대로 들고 다니는 예외. */
export class PortalApiError extends Error {
  readonly code: string
  readonly detail: unknown
  readonly status: number

  constructor(status: number, body: Partial<ApiError>) {
    super(body.message ?? '요청을 처리하지 못했습니다.')
    this.name = 'PortalApiError'
    this.status = status
    this.code = body.code ?? 'UNKNOWN'
    this.detail = body.detail
  }
}

function readCookie(name: string): string | null {
  const hit = document.cookie.split('; ').find((c) => c.startsWith(name + '='))
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : null
}

/**
 * 세션이 있을 법한가. 액세스 토큰은 HttpOnly라 못 읽으므로 **함께 심어 준 CSRF 쿠키의
 * 존재**로 판단한다. 확답이 아니라 힌트다 — 진위는 서버(`/auth/me`)가 정한다.
 */
export function hasSession(): boolean {
  return readCookie(CSRF_COOKIE) !== null
}

/** 401 발생 시 앱이 로그인 화면으로 보낼 수 있게 알린다(순환 import 회피). */
type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler = () => {}
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler
}

interface RequestOptions {
  method?: string
  body?: unknown
  query?: Record<string, string | number | boolean | null | undefined>
  /** 로그인처럼 401을 정상 흐름으로 다루는 호출은 자동 로그아웃을 막는다. */
  skipAuthRedirect?: boolean
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(BASE + path, window.location.origin)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== null && value !== undefined && value !== '') {
        url.searchParams.set(key, String(value))
      }
    }
  }
  return url.pathname + url.search
}

/**
 * 액세스 토큰은 30분이라 화면을 오래 켜 두면 반드시 만료된다. 401마다 로그인 화면으로
 * 보내면 30분마다 쫓겨나므로, **한 번 갱신해 보고 재시도한다.**
 *
 * 갱신은 **하나만 돌린다** — 401이 동시에 여럿 나면 refresh가 회전 중에 겹쳐
 * 서로의 토큰을 무효로 만든다(서버가 재사용을 탈취로 보고 세션을 끊는다).
 */
let refreshing: Promise<boolean> | null = null

function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(BASE + '/auth/refresh', {
    method: 'POST',
    credentials: 'same-origin',
    headers: csrfHeaders(),
  })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export function csrfHeaders(): Record<string, string> {
  const token = readCookie(CSRF_COOKIE)
  return token ? { [CSRF_HEADER]: token } : {}
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, skipAuthRedirect } = options

  const send = (): Promise<Response> => {
    const headers: Record<string, string> = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (!SAFE_METHODS.has(method)) Object.assign(headers, csrfHeaders())
    return fetch(buildUrl(path, query), {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  }

  let response: Response
  try {
    response = await send()
    if (response.status === 401 && !skipAuthRedirect && (await refreshSession())) {
      response = await send()
    }
  } catch (cause) {
    // 네트워크 단절을 서버 오류처럼 보이게 하면 원인 파악이 늦어진다.
    throw new PortalApiError(0, {
      code: 'NETWORK_ERROR',
      message: '서버에 연결할 수 없습니다.',
      detail: String(cause),
    })
  }

  // 갱신까지 해봤는데도 401이면 세션이 정말 끝난 것이다.
  if (response.status === 401 && !skipAuthRedirect) {
    onUnauthorized()
  }

  const text = await response.text()
  const payload: unknown = text ? safeJson(text) : null

  if (!response.ok) {
    throw new PortalApiError(response.status, (payload ?? {}) as Partial<ApiError>)
  }
  return payload as T
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return { code: 'INVALID_RESPONSE', message: text.slice(0, 200) }
  }
}

export const api = {
  get: <T>(path: string, query?: RequestOptions['query']) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  del: <T>(path: string, query?: RequestOptions['query']) =>
    request<T>(path, { method: 'DELETE', query }),
}
