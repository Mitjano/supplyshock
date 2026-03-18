<template>
  <div class="market-heatmap">
    <h3 class="heatmap-title">{{ t('homeDashboard.marketHeatmap') }}</h3>
    <div class="heatmap-grid">
      <div
        v-for="tile in tiles"
        :key="tile.commodity"
        class="heatmap-tile"
        :style="tileStyle(tile)"
        :title="`${tile.commodity}: ${tile.change_24h > 0 ? '+' : ''}${tile.change_24h.toFixed(2)}%`"
      >
        <span class="tile-name">{{ formatName(tile.commodity) }}</span>
        <span class="tile-change">{{ tile.change_24h > 0 ? '+' : '' }}{{ tile.change_24h.toFixed(2) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  data: { commodity: string; change_24h: number; price: number }[]
}>()

const tiles = computed(() =>
  [...props.data].sort((a, b) => Math.abs(b.change_24h) - Math.abs(a.change_24h))
)

function tileStyle(tile: { change_24h: number }) {
  const change = tile.change_24h
  const absChange = Math.min(Math.abs(change), 5)
  const intensity = 0.15 + (absChange / 5) * 0.55
  const bg = change >= 0
    ? `rgba(34, 197, 94, ${intensity})`
    : `rgba(239, 68, 68, ${intensity})`
  // Size proportional to % change (min 80px, max 140px)
  const size = 80 + (absChange / 5) * 60
  return {
    background: bg,
    minWidth: `${size}px`,
    minHeight: `${size * 0.6}px`,
  }
}

function formatName(name: string) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
</script>

<style scoped>
.market-heatmap {
  width: 100%;
}

.heatmap-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  color: var(--ss-text-primary);
}

.heatmap-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.heatmap-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.75rem;
  border-radius: var(--ss-radius);
  cursor: default;
  transition: transform var(--ss-transition-fast);
  flex: 1 1 auto;
}

.heatmap-tile:hover {
  transform: scale(1.03);
}

.tile-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ss-text-primary);
  text-transform: capitalize;
  white-space: nowrap;
}

.tile-change {
  font-size: 0.8rem;
  font-weight: 700;
  margin-top: 0.15rem;
}
</style>
