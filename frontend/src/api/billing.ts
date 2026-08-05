import { api } from './client'

export interface BillingConfig {
  configured: boolean
  scp_account_id: string | null
  api_endpoint: string | null
  monthly_alert_krw: number | null
  last_verified_at: string | null
}

export interface BillingTrend {
  start: string
  end: string
  total_krw: number
  daily: { date: string; krw: number }[]
  by_category: { label: string; krw: number }[]
  by_item: { label: string; krw: number }[]
  record_count: number
  tag: string | null
  tagged_resource_count: number | null
}

export interface BillingRule {
  id: number
  kind: string
  condition: string
  mapping_label: string | null
  is_active: boolean
}

export const billingApi = {
  config: () => api.get<BillingConfig>('/billing/config'),
  /** 키는 요청으로만 나가고 응답에는 실리지 않는다. 서버가 저장 전 실제 조회로 검증한다. */
  putConfig: (payload: {
    access_key: string
    secret_key: string
    monthly_alert_krw?: number | null
  }) => api.put<BillingConfig>('/billing/config', payload),
  trend: (days = 30, tag?: string) =>
    api.get<BillingTrend>(
      `/billing/trend?days=${days}${tag ? `&tag=${encodeURIComponent(tag)}` : ''}`,
    ),
  rules: () => api.get<BillingRule[]>('/billing/rules'),
  addRule: (payload: { kind: string; condition: string; mapping_label?: string }) =>
    api.post<BillingRule>('/billing/rules', payload),
  removeRule: (id: number) => api.del<{ ok: boolean }>(`/billing/rules/${id}`),
}
