<template>
  <button
    class="watchlist-star"
    :class="{ active: isWatched }"
    :title="isWatched ? 'Remove from watchlist' : 'Add to watchlist'"
    @click.stop="toggle"
  >
    <i :class="['pi', isWatched ? 'pi-star-fill' : 'pi-star']" />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWatchlistStore } from '@/stores/useWatchlistStore'

const props = defineProps<{
  commodity: string
}>()

const watchlist = useWatchlistStore()
const isWatched = computed(() => watchlist.isWatched(props.commodity))

async function toggle() {
  await watchlist.toggleCommodity(props.commodity)
}
</script>

<style scoped>
.watchlist-star {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--ss-text-muted);
  font-size: 1rem;
  padding: 0.25rem;
  transition: color var(--ss-transition-fast), transform var(--ss-transition-fast);
}

.watchlist-star:hover {
  color: #f59e0b;
  transform: scale(1.15);
}

.watchlist-star.active {
  color: #f59e0b;
}
</style>
