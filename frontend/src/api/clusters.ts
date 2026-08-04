import { api } from './client'
import type {
  Cluster,
  ClusterCreate,
  ClusterSummary,
  CredentialOut,
  OkResponse,
  RestTestResult,
} from '@/types/api'

export const clusterApi = {
  list: () => api.get<ClusterSummary[]>('/clusters'),
  create: (payload: ClusterCreate) => api.post<Cluster>('/clusters', payload),
  get: (cid: number) => api.get<Cluster>(`/clusters/${cid}`),
  update: (cid: number, payload: Partial<ClusterCreate>) =>
    api.patch<Cluster>(`/clusters/${cid}`, payload),
  remove: (cid: number) => api.del<OkResponse>(`/clusters/${cid}`),
  putCredential: (cid: number, kind: 'SLURM_JWT' | 'SSH_KEY', value: string) =>
    api.put<CredentialOut>(`/clusters/${cid}/credentials`, { kind, value }),
  testRest: (cid: number) => api.post<RestTestResult>(`/clusters/${cid}/test-rest`),
}
