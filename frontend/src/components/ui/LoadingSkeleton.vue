<template>
  <div class="skeleton-container" :style="containerStyle">
    <div v-if="variant === 'card'" class="skeleton-card">
      <div class="skeleton-bar" :style="{ height: height || '200px' }" />
    </div>
    <div v-else-if="variant === 'table'" class="skeleton-table">
      <div v-for="i in rows" :key="i" class="skeleton-row">
        <div class="skeleton-bar" style="width: 30%; height: 14px" />
        <div class="skeleton-bar" style="width: 20%; height: 14px" />
        <div class="skeleton-bar" style="width: 25%; height: 14px" />
      </div>
    </div>
    <div v-else-if="variant === 'chart'" class="skeleton-chart">
      <div class="skeleton-bar" :style="{ height: height || '300px' }" />
    </div>
    <div v-else class="skeleton-bar" :style="{ width: width || '100%', height: height || '16px' }" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  variant?: 'text' | 'card' | 'table' | 'chart'
  width?: string
  height?: string
  rows?: number
}>()

const containerStyle = computed(() => ({}))
</script>

<style scoped>
.skeleton-container {
  width: 100%;
}

.skeleton-bar {
  background: linear-gradient(90deg, var(--ss-bg-elevated) 25%, var(--ss-border-light) 50%, var(--ss-bg-elevated) 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: var(--ss-radius-sm, 4px);
}

.skeleton-card {
  border-radius: var(--ss-radius);
  overflow: hidden;
}

.skeleton-table {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
}

.skeleton-row {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.skeleton-chart {
  border-radius: var(--ss-radius);
  overflow: hidden;
}

@keyframes skeleton-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
</style>
