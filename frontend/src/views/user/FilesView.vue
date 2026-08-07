<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fileApi, type BrowseResponse, type FileEntry, type StorageResponse } from '@/api/files'
import { useClusterStore } from '@/stores/cluster'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import Meter from '@/components/ui/Meter.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-07 — 로그인 노드 SFTP 경유 조회(U-FM-01) + 업/다운로드(U-FM-02)·조작(U-FM-04). */
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

/* --- 파일 조작 (U-FM-02 업/다운로드 · U-FM-04 생성·삭제·이름변경·이동) --- */

const busy = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

type DialogKind = 'mkdir' | 'touch' | 'rename' | 'move'
const dialog = ref<{
  kind: DialogKind
  title: string
  label: string
  hint?: string
  value: string
  entry?: FileEntry
} | null>(null)
const dialogError = ref<unknown>(null)

const here = computed(() => (listing.value?.path ?? '').replace(/\/$/, ''))
const join = (dir: string, name: string) => `${dir.replace(/\/$/, '')}/${name}`

/**
 * 조작 → 실패면 화면에 남기고, 성공이면 **현재 디렉터리를 다시 읽는다.**
 * 서버가 정규화한 경로를 돌려주지만 목록은 다시 받아야 다른 변경까지 반영된다.
 */
async function run(
  action: () => Promise<unknown>,
  target: 'dialog' | 'page' = 'dialog',
): Promise<boolean> {
  const cid = clusters.selectedId
  if (!cid) return false
  const fail = (e: unknown) => {
    if (target === 'dialog') dialogError.value = e
    else errors.value.files = e
  }
  busy.value = true
  fail(null)
  try {
    await action()
    await open(here.value)
    return true
  } catch (e) {
    fail(e)
    return false
  } finally {
    busy.value = false
  }
}

function ask(kind: DialogKind, entry?: FileEntry) {
  dialogError.value = null
  const preset: Record<DialogKind, { title: string; label: string; hint?: string; value: string }> = {
    mkdir: { title: '디렉터리 생성', label: '이름', value: '' },
    touch: { title: '파일 생성', label: '이름', value: '' },
    rename: { title: '이름 변경', label: '새 이름', value: entry?.name ?? '' },
    move: {
      title: '옮기기',
      label: '옮길 위치(디렉터리 경로)',
      hint: '홈 디렉터리 안에서만 옮길 수 있습니다.',
      value: here.value,
    },
  }
  dialog.value = { kind, entry, ...preset[kind] }
}

async function submitDialog() {
  const d = dialog.value
  const cid = clusters.selectedId
  if (!d || !cid) return
  const value = d.value.trim()
  if (!value) return
  const source = d.entry ? join(here.value, d.entry.name) : ''
  const ok = await run(async () => {
    if (d.kind === 'mkdir') await fileApi.mkdir(cid, join(here.value, value))
    else if (d.kind === 'touch') await fileApi.touch(cid, join(here.value, value))
    else if (d.kind === 'rename') await fileApi.move(cid, source, join(here.value, value))
    else await fileApi.move(cid, source, join(value, d.entry!.name))
  })
  if (ok) dialog.value = null
}

/**
 * 디렉터리는 **안의 항목까지 지운다는 것을 먼저 알린다.** 백엔드 기본값은 비재귀라,
 * 여기서 명시적으로 요청할 때만 트리가 지워진다.
 */
async function remove(entry: FileEntry) {
  const cid = clusters.selectedId
  if (!cid) return
  const message = entry.is_dir
    ? `'${entry.name}' 폴더와 그 안의 모든 항목을 삭제합니다. 되돌릴 수 없습니다.`
    : `'${entry.name}'을(를) 삭제합니다. 되돌릴 수 없습니다.`
  if (!confirm(message)) return
  await run(() => fileApi.remove(cid, join(here.value, entry.name), entry.is_dir), 'page')
}

async function download(entry: FileEntry) {
  const cid = clusters.selectedId
  if (!cid) return
  busy.value = true
  errors.value.files = null
  try {
    await fileApi.download(cid, join(here.value, entry.name), entry.name)
  } catch (e) {
    errors.value.files = e
  } finally {
    busy.value = false
  }
}

/** 여러 개를 고르면 순서대로 올린다 — 하나가 실패하면 거기서 멈추고 알린다. */
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const cid = clusters.selectedId
  const files = Array.from(input.files ?? [])
  input.value = '' // 같은 파일을 다시 골라도 change가 나게 비운다
  if (!cid || !files.length) return
  busy.value = true
  errors.value.files = null
  try {
    for (const file of files) await fileApi.upload(cid, here.value, file)
  } catch (e) {
    errors.value.files = e
  } finally {
    busy.value = false
    await open(here.value)
  }
}
</script>

<template>
  <PageHead
    title="파일 관리자"
    :crumbs="['HPC Portal', '작업 환경']"
    :sub="`로그인 노드 경유 SFTP · ${clusters.selectedName}`"
  >
    <template #actions>
      <!-- 파일 선택창은 숨겨 두고 버튼으로 연다 -->
      <input ref="fileInput" type="file" multiple class="hidden" @change="upload" />
      <Btn :disabled="!listing || busy" @click="fileInput?.click()">
        {{ busy ? '처리 중…' : '⬆ 업로드' }}
      </Btn>
      <Btn :disabled="!listing || busy" @click="ask('mkdir')">＋ 디렉터리</Btn>
      <Btn :disabled="!listing || busy" @click="ask('touch')">＋ 파일</Btn>
      <Btn :disabled="busy" @click="open(listing?.path)">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <!-- Billing·Job 제출과 같은 배치 — 넓은 본문(브라우저) + 좁은 현황 열 -->
  <div class="grid lg:grid-cols-[1fr_420px] gap-5 items-start">
    <Card title="파일 브라우저" flush>
      <template #title-extra><Fid id="U-FM-01" /></template>
      <ErrorNote :error="errors.files" class="m-4" />

      <div v-if="listing" class="px-4 py-3 border-b border-line flex flex-wrap items-center gap-2">
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
          { key: 'act', label: '', width: '240px' },
        ]"
      >
        <tr v-if="parent" class="border-b border-line">
          <td class="px-3.5 py-2.5" colspan="5">
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
          <td class="px-3.5 py-2.5">
            <div class="flex justify-end gap-1.5">
              <!-- 디렉터리는 내려받을 수 없다(서버도 거부한다) — 버튼 자체를 감춘다 -->
              <Btn v-if="!e.is_dir" size="sm" :disabled="busy" @click="download(e)">받기</Btn>
              <Btn size="sm" :disabled="busy" @click="ask('rename', e)">이름</Btn>
              <Btn size="sm" :disabled="busy" @click="ask('move', e)">옮기기</Btn>
              <Btn size="sm" variant="danger" :disabled="busy" @click="remove(e)">삭제</Btn>
            </div>
          </td>
        </tr>
      </Table>
    </Card>

    <Card title="스토리지 사용량" flush>
      <template #title-extra><Fid id="A-DB-05" /></template>
      <ErrorNote :error="errors.storage" class="m-4" />
      <Empty v-if="!storage?.targets.length && !errors.storage" text="스토리지 정보가 없습니다." />
      <!-- 좁은 열이라 표가 아니라 세로로 쌓는다. 표로 두면 6열이 가로 스크롤에 갇힌다. -->
      <div v-else-if="storage" class="divide-y divide-line">
        <div v-for="t in storage.targets" :key="t.label" class="p-4">
          <div class="flex items-baseline gap-2">
            <b class="text-[15px]">{{ t.label }}</b>
            <span class="mono text-[13px] text-ink-3 break-all">{{ t.path }}</span>
          </div>
          <template v-if="t.exists">
            <p class="mt-0.5 mono text-[12.5px] text-ink-3 break-all">{{ t.filesystem }}</p>
            <Meter label="" :value="t.used_pct ?? 0" :caption="`${t.used_pct ?? 0}%`" class="mt-2.5" />
            <div class="mt-2 flex justify-between mono text-[13px]">
              <span class="text-ink-3">사용 <b class="text-ink">{{ size(t.used_bytes ?? 0) }}</b></span>
              <span class="text-ink-3">여유 <b class="text-ink">{{ size(t.avail_bytes ?? 0) }}</b></span>
            </div>
          </template>
          <!-- 미구축 경로는 행을 지우지 않고 '없음'으로 남긴다 — 설정은 됐지만 없다는 뜻 -->
          <p v-else class="mt-1 text-[13px] text-ink-3">없음</p>
        </div>
      </div>
    </Card>
  </div>

  <!-- 생성·이름 변경·옮기기는 입력이 하나뿐이라 모달 하나를 나눠 쓴다 -->
  <Modal v-if="dialog" :title="dialog.title" @close="dialog = null">
    <ErrorNote :error="dialogError" class="mb-3" />
    <label class="block text-[13px] text-ink-3">
      {{ dialog.label }}
      <input
        v-model="dialog.value"
        class="w-full mt-1 px-3 py-2 border border-line rounded-lg text-[14.5px] mono outline-none focus:border-brand-500"
        autofocus
        @keyup.enter="submitDialog"
      />
    </label>
    <p class="mt-2 text-[12.5px] text-ink-3">
      {{ dialog.hint ?? `현재 위치: ${here}` }}
    </p>
    <template #foot>
      <Btn :disabled="busy" @click="dialog = null">취소</Btn>
      <Btn variant="primary" :disabled="busy || !dialog.value.trim()" @click="submitDialog">
        {{ busy ? '처리 중…' : '확인' }}
      </Btn>
    </template>
  </Modal>
</template>
