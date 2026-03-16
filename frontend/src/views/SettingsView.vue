<template>
  <div class="view-container fade-in">
    <h1>{{ t('nav.settings') }}</h1>
    <p class="text-secondary">{{ t('common.comingSoon') }}</p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
