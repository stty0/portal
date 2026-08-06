<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'outline' | 'ghost' | 'danger'
    size?: 'sm' | 'md'
    disabled?: boolean
    type?: 'button' | 'submit'
  }>(),
  { variant: 'outline', size: 'md', type: 'button' },
)
const VARIANT = {
  primary: 'bg-brand-700 text-white border-brand-700 hover:bg-brand-800',
  outline: 'bg-surface text-ink-2 border-line-dark hover:bg-bg',
  ghost: 'bg-transparent text-ink-2 border-transparent hover:bg-bg',
  danger: 'bg-err text-white border-err hover:brightness-95',
} as const
const SIZE = { sm: 'text-[13px] px-2.5 py-1', md: 'text-[14.5px] px-3.5 py-2' } as const
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    class="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap border rounded-lg font-semibold transition-colors disabled:opacity-45 disabled:cursor-not-allowed"
    :class="[VARIANT[variant], SIZE[size]]"
  >
    <slot />
  </button>
</template>
