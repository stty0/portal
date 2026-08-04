import { api } from './client'
import type { AdConnection, AdSyncResult, Page, User } from '@/types/api'

export const userApi = {
  list: (query: Record<string, string | number | undefined> = {}) =>
    api.get<Page<User>>('/users', query),
  get: (guid: string) => api.get<User>(`/users/${guid}`),
  update: (guid: string, payload: { role?: string; is_active?: boolean }) =>
    api.patch<User>(`/users/${guid}`, payload),
}

export const adApi = {
  connection: () => api.get<AdConnection>('/ad/connection'),
  updateConnection: (payload: Partial<AdConnection> & { bind_password?: string }) =>
    api.put<AdConnection>('/ad/connection', payload),
  test: () => api.post<{ ok: boolean }>('/ad/connection/test'),
  sync: () => api.post<AdSyncResult>('/ad/sync'),
}
