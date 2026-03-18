<template>
  <div class="error-state">
    <i class="pi pi-exclamation-triangle error-icon" />
    <h3 class="error-title">{{ title || t('common.error') }}</h3>
    <p v-if="description" class="error-desc">{{ description }}</p>
    <button v-if="retryable" class="ss-btn ss-btn--outline" @click="$emit('retry')">
      <i class="pi pi-refresh" /> {{ t('common.retry') }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

defineProps<{
  title?: string
  description?: string
  retryable?: boolean
}>()

defineEmits<{
  retry: []
}>()
</script>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  text-align: center;
  min-height: 200px;
}

.error-icon {
  font-size: 2.5rem;
  color: var(--ss-danger);
  margin-bottom: 1rem;
}

.error-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--ss-text-primary);
  margin: 0 0 0.5rem;
}

.error-desc {
  font-size: 0.875rem;
  color: var(--ss-text-muted);
  max-width: 400px;
  margin: 0 0 1rem;
  line-height: 1.5;
}
</style>
