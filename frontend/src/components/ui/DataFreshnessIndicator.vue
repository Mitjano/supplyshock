<template>
  <span class="freshness" :class="freshness">
    <span class="freshness-dot" />
    <span class="freshness-text">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  lastUpdated: string | Date | null
}>()

const freshness = computed(() => {
  if (!props.lastUpdated) return 'stale'
  const diff = Date.now() - new Date(props.lastUpdated).getTime()
  if (diff < 60_000) return 'live'
  if (diff < 300_000) return 'recent'
  if (diff < 900_000) return 'delayed'
  return 'stale'
})

const label = computed(() => {
  if (!props.lastUpdated) return t('common.noData')
  const diff = Date.now() - new Date(props.lastUpdated).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h`
})
</script>

<style scoped>
.freshness {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--ss-text-muted);
}

.freshness-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.live .freshness-dot { background: #22c55e; box-shadow: 0 0 4px #22c55e; }
.recent .freshness-dot { background: #22c55e; }
.delayed .freshness-dot { background: #f59e0b; }
.stale .freshness-dot { background: #6b7280; }
</style>
