<template>
  <div class="empty-state">
    <i :class="['pi', icon]" class="empty-icon" />
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  description?: string
}>()
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  text-align: center;
  min-height: 200px;
}

.empty-icon {
  font-size: 2.5rem;
  color: var(--ss-text-muted);
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--ss-text-primary);
  margin: 0 0 0.5rem;
}

.empty-desc {
  font-size: 0.875rem;
  color: var(--ss-text-muted);
  max-width: 400px;
  margin: 0;
  line-height: 1.5;
}
</style>
