<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const props = defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()

// ESC 닫기 — 정적 프로토타입의 모달 규약과 동일하게 유지한다.
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div
    class="fixed inset-0 z-50 bg-black/35 flex items-start justify-center p-6 overflow-y-auto"
    @click.self="emit('close')"
  >
    <div
      class="bg-surface rounded-card shadow-pop w-full mt-[6vh]"
      :class="props.wide ? 'max-w-4xl' : 'max-w-xl'"
      role="dialog"
      aria-modal="true"
    >
      <header class="flex items-center gap-2 px-5 py-3.5 border-b border-line">
        <h3 class="flex-1 text-[15px] font-semibold text-ink flex items-center gap-2">
          {{ title }}<slot name="title-extra" />
        </h3>
        <button
          class="w-7 h-7 rounded-md text-ink-3 hover:bg-bg text-lg leading-none"
          aria-label="닫기"
          @click="emit('close')"
        >✕</button>
      </header>
      <div class="p-5 max-h-[70vh] overflow-y-auto"><slot /></div>
      <footer v-if="$slots.foot" class="flex justify-end gap-2 px-5 py-3.5 border-t border-line">
        <slot name="foot" />
      </footer>
    </div>
  </div>
</template>
