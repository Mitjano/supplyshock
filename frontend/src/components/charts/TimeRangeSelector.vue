<template>
  <div class="time-range-selector">
    <button
      v-for="range in ranges"
      :key="range"
      class="range-btn"
      :class="{ active: modelValue === range }"
      @click="$emit('update:modelValue', range)"
    >
      {{ range }}
    </button>
  </div>
</template>

<script setup lang="ts">
export type TimeRange = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | '5Y' | 'ALL'

defineProps<{
  modelValue: TimeRange
}>()

defineEmits<{
  (e: 'update:modelValue', value: TimeRange): void
}>()

const ranges: TimeRange[] = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y', 'ALL']
</script>

<style scoped>
.time-range-selector {
  display: flex;
  gap: var(--ss-space-xs, 4px);
  flex-wrap: wrap;
}

.range-btn {
  padding: var(--ss-space-xs, 4px) var(--ss-space-md, 12px);
  border: 1px solid var(--ss-border, #475569);
  border-radius: var(--ss-radius-md, 6px);
  background: transparent;
  color: var(--ss-text-secondary, #cbd5e1);
  font-size: var(--ss-text-xs, 0.75rem);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--ss-transition-fast, 150ms ease);
  line-height: 1.4;
}

.range-btn:hover {
  background: var(--ss-bg-hover, #475569);
  color: var(--ss-text-primary, #f8fafc);
}

.range-btn.active {
  background: var(--ss-accent, #3b82f6);
  border-color: var(--ss-accent, #3b82f6);
  color: #fff;
}
</style>
