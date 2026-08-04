import { api } from './client'
import type {
  LoginResponse,
  Me,
  OkResponse,
  SetupProbeResponse,
  SetupRequest,
  SetupStatus,
} from '@/types/api'

export const authApi = {
  setupStatus: () => api.get<SetupStatus>('/auth/setup-status'),
  // 1단계: AD bind 검증 + 관리자 후보 조회 (저장 없음)
  setupProbe: (payload: Record<string, unknown>) =>
    api.post<SetupProbeResponse>('/auth/setup/probe', payload),
  setup: (payload: SetupRequest) => api.post<OkResponse>('/auth/setup', payload),
  // 로그인 401은 "잘못된 자격증명"이라 세션 만료 처리를 하면 안 된다.
  login: (username: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { username, password }, { skipAuthRedirect: true }),
  logout: () => api.post<OkResponse>('/auth/logout'),
  me: () => api.get<Me>('/auth/me'),
}
