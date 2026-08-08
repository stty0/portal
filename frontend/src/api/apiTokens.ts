import { api } from './client'
import type { OkResponse } from '@/types/api'

export interface ApiToken {
  id: number
  name: string
  prefix: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
}

/** 발급 응답에만 원문이 담긴다 — 목록에는 없다. */
export interface ApiTokenCreated extends ApiToken {
  token: string
}

export const apiTokenApi = {
  list: () => api.get<ApiToken[]>('/me/api-tokens'),
  create: (name: string, expires_in_days: number | null) =>
    api.post<ApiTokenCreated>('/me/api-tokens', { name, expires_in_days }),
  revoke: (id: number) => api.del<OkResponse>(`/me/api-tokens/${id}`),
}
