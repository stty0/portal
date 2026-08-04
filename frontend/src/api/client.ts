import type { ApiError } from '@/types/api'

const BASE = '/api/v1'
const TOKEN_KEY = 'hpc-portal-token'

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

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
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

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, skipAuthRedirect } = options
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (cause) {
    // 네트워크 단절을 서버 오류처럼 보이게 하면 원인 파악이 늦어진다.
    throw new PortalApiError(0, {
      code: 'NETWORK_ERROR',
      message: '서버에 연결할 수 없습니다.',
      detail: String(cause),
    })
  }

  if (response.status === 401 && !skipAuthRedirect) {
    setToken(null)
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
