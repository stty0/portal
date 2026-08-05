<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fileApi, type BrowseResponse, type StorageResponse } from '@/api/files'
import { useClusterStore } from '@/stores/cluster'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import Meter from '@/components/ui/Meter.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-07 — 로그인 노드 SFTP 경유 조회. 업/다운로드·편집은 아직 없다. */
const clusters = useClusterStore()
const listing = ref<BrowseResponse | null>(null)
const storage = ref<StorageResponse | null>(null)
const loading = ref(false)
const errors = ref<{ files: unknown; storage: unknown }>({ files: null, storage: null })

async function open(path?: string) {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  const [f, s] = await Promise.allSettled([fileApi.browse(cid, path), fileApi.storage(cid)])
  listing.value = f.status === 'fulfilled' ? f.value : null
  storage.value = s.status === 'fulfilled' ? s.value : null
  errors.value = {
    files: f.status === 'rejected' ? f.reason : null,
    storage: s.status === 'rejected' ? s.reason : null,
  }
  loading.value = false
}
watch(() => clusters.selectedId, () => open(), { immediate: true })

/**
 * 브레드크럼은 **허용 루트 아래 구간만** 만든다.
 * 루트 위 조각을 링크로 보여주면 눌러도 403이라 눌러볼 이유가 없다.
 */
const root = computed(() => {
  const path = listing.value?.path ?? ''
  return (listing.value?.roots ?? []).find(
    (r) => path === r || path.startsWith(r.replace(/\/$/, '') + '/'),
  )
})

const crumbs = computed(() => {
  const path = listing.value?.path ?? ''
  const base = root.value
  if (!base || path === base) return []
  const rest = path.slice(base.length).split('/').filter(Boolean)
  return rest.map((name, i) => ({ name, path: base + '/' + rest.slice(0, i + 1).join('/') }))
})

/** 루트에 있으면 상위 이동을 감춘다 — 홈 위로는 올라갈 수 없다. */
const parent = computed(() => {
  const path = listing.value?.path ?? ''
  if (!root.value || path === root.value) return null
  return path.replace(/\/[^/]+\/?$/, '') || '/'
})

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = bytes / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(1)} ${units[i]}`
}

function when(mtime: number | null): string {
  return mtime ? new Date(mtime * 1000).toLocaleString('ko-KR') : '—'
}
</script>

<template>
  <PageHead
    title="파일 관리자"
    :crumbs="['HPC Portal', '작업 환경']"
    :sub="`로그인 노드 경유 SFTP · ${clusters.selectedName}`"
  >
    <template #actions><Btn @click="open(listing?.path)">↻ 새로고침</Btn></template>
  </PageHead>

  <div class="space-y-5">
    <Card title="파일 브라우저" flush>
      <template #title-extra><Fid id="U-FM-01" /></template>
      <ErrorNote :error="errors.files" class="m-4" />

      <div v-if="listing" class="px-4 py-3 border-b border-line flex flex-wrap items-center gap-2">
        <!-- 미구축 경로는 숨기지 않고 '없음'으로 알린다 — 눌러서 실패하는 것보다 낫다 -->
        <template v-for="s in listing.shortcuts" :key="s.path">
          <Chip v-if="s.exists" tone="brand" class="cursor-pointer" @click="open(s.path)">
            {{ s.label }}
          </Chip>
          <Chip v-else tone="gray" :title="`${s.path} — 아직 구성되지 않았습니다`">
            {{ s.label }} 없음
          </Chip>
        </template>
        <span class="mx-1 text-line">|</span>
        <button
          class="text-[13.5px] text-brand-700 hover:underline mono"
          @click="open(root)"
        >{{ root }}</button>
        <template v-for="c in crumbs" :key="c.path">
          <span class="text-ink-3">/</span>
          <button
            class="text-[13.5px] text-brand-700 hover:underline mono"
            @click="open(c.path)"
          >{{ c.name }}</button>
        </template>
      </div>

      <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>
      <Empty
        v-else-if="!listing && !errors.files"
        text="클러스터를 선택하면 파일을 조회합니다."
      />
      <Table
        v-else-if="listing"
        :columns="[
          { key: 'name', label: '이름' },
          { key: 'size', label: '크기', num: true },
          { key: 'mtime', label: '수정 시각', num: true },
          { key: 'mode', label: '권한' },
        ]"
      >
        <tr v-if="parent" class="border-b border-line">
          <td class="px-3.5 py-2.5" colspan="4">
            <button class="text-brand-700 hover:underline mono" @click="open(parent)">
              ⬑ 상위 디렉터리
            </button>
          </td>
        </tr>
        <tr v-for="e in listing.entries" :key="e.name" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5">
            <button
              v-if="e.is_dir"
              class="text-brand-700 hover:underline mono font-semibold"
              @click="open(`${listing.path.replace(/\/$/, '')}/${e.name}`)"
            >📁 {{ e.name }}</button>
            <span v-else class="mono">{{ e.name }}</span>
          </td>
          <td class="px-3.5 py-2.5 mono text-right">{{ e.is_dir ? '—' : size(e.size) }}</td>
          <td class="px-3.5 py-2.5 mono text-right text-[13px]">{{ when(e.mtime) }}</td>
          <td class="px-3.5 py-2.5 mono text-[13px] text-ink-3">{{ e.mode }}</td>
        </tr>
      </Table>
    </Card>

    <Card title="스토리지 사용량" flush>
      <template #title-extra><Fid id="A-DB-05" /></template>
      <ErrorNote :error="errors.storage" class="m-4" />
      <Empty v-if="!storage?.targets.length && !errors.storage" text="스토리지 정보가 없습니다." />
      <Table
        v-else-if="storage"
        :columns="[
          { key: 'label', label: '구분', width: '110px' },
          { key: 'path', label: '경로' },
          { key: 'fs', label: '파일시스템' },
          { key: 'use', label: '사용률', width: '200px' },
          { key: 'used', label: '사용', num: true },
          { key: 'avail', label: '여유', num: true },
        ]"
      >
        <tr v-for="t in storage.targets" :key="t.label" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 font-semibold">{{ t.label }}</td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ t.path }}</td>
          <template v-if="t.exists">
            <td class="px-3.5 py-2.5 mono text-[13px] text-ink-3">{{ t.filesystem }}</td>
            <td class="px-3.5 py-2.5">
              <Meter label="" :value="t.used_pct ?? 0" :caption="`${t.used_pct ?? 0}%`" />
            </td>
            <td class="px-3.5 py-2.5 mono text-right">{{ size(t.used_bytes ?? 0) }}</td>
            <td class="px-3.5 py-2.5 mono text-right">{{ size(t.avail_bytes ?? 0) }}</td>
          </template>
          <!-- 미구축 경로는 행을 지우지 않고 '없음'으로 남긴다 — 설정은 됐지만 없다는 뜻 -->
          <td v-else class="px-3.5 py-2.5 text-ink-3" colspan="4">없음</td>
        </tr>
      </Table>
    </Card>
  </div>
</template>
