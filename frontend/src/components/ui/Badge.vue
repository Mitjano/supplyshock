<template>
  <span class="ss-badge" :class="`badge-${variant}`">
    {{ text }}
  </span>
</template>

<script setup lang="ts">
defineProps<{
  text: string
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'neutral'
}>()
</script>

<script lang="ts">
export default {
  inheritAttrs: true,
}
</script>

<style scoped>
.ss-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--ss-radius-full, 9999px);
  font-size: var(--ss-text-xs, 0.75rem);
  font-weight: var(--ss-font-medium, 500);
  line-height: 1.4;
  white-space: nowrap;
}

.badge-success {
  background: var(--ss-success-bg, rgba(34, 197, 94, 0.15));
  color: var(--ss-success, #22c55e);
}

.badge-warning {
  background: var(--ss-warning-bg, rgba(245, 158, 11, 0.15));
  color: var(--ss-warning, #f59e0b);
}

.badge-danger {
  background: var(--ss-danger-bg, rgba(239, 68, 68, 0.15));
  color: var(--ss-danger, #ef4444);
}

.badge-info {
  background: var(--ss-info-bg, rgba(6, 182, 212, 0.15));
  color: var(--ss-info, #06b6d4);
}

.badge-neutral {
  background: var(--ss-neutral-bg, rgba(148, 163, 184, 0.15));
  color: var(--ss-neutral, #94a3b8);
}
</style>
