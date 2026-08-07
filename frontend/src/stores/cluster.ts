import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { clusterApi } from '@/api/clusters'
import type { ClusterSummary } from '@/types/api'

const STORAGE_KEY = 'hpc-portal-cluster'

/**
 * 전역 클러스터 스코프 — 톱바 선택기가 정본이다.
 *
 * 정적 프로토타입은 페이지마다 `applyCluster()`를 복붙해 두었는데(design/*.html),
 * 운영 화면(노드·Job·계정·QOS 등)은 "선택된 클러스터 1개" 기준으로 보여야 하므로
 * 여기 한 곳에서만 관리한다. 집계 화면(대시보드·리포트·Billing)은 예외로 전 클러스터를 본다.
 */
export const useClusterStore = defineStore('cluster', () => {
  const clusters = ref<ClusterSummary[]>([])
  const selectedId = ref<number | null>(null)
  const loaded = ref(false)

  const selected = computed(
    () => clusters.value.find((c) => c.id === selectedId.value) ?? null,
  )
  /** 화면 부제목용 표시명. 이름은 REST 연결 전까지 없으므로 별칭이 먼저다. */
  const selectedName = computed(
    () => selected.value?.alias || selected.value?.name || '—',
  )

  async function load(): Promise<void> {
    clusters.value = await clusterApi.list()
    loaded.value = true

    const saved = Number(localStorage.getItem(STORAGE_KEY))
    const savedExists = clusters.value.some((c) => c.id === saved)
    if (savedExists) {
      selectedId.value = saved
      return
    }
    // 저장된 선택이 없거나 삭제됐으면 기본 클러스터 → 없으면 첫 번째
    const fallback = clusters.value.find((c) => c.is_default) ?? clusters.value[0]
    selectedId.value = fallback?.id ?? null
  }

  function select(id: number): void {
    selectedId.value = id
    localStorage.setItem(STORAGE_KEY, String(id))
  }

  function reset(): void {
    clusters.value = []
    selectedId.value = null
    loaded.value = false
  }

  return { clusters, selectedId, selected, selectedName, loaded, load, select, reset }
})
