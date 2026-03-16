<template>
  <div v-if="auth.loading" class="app-loading">
    <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: var(--ss-accent)" />
  </div>
  <template v-else>
    <AppLayout v-if="auth.isAuthenticated && !isLoginRoute">
      <router-view />
    </AppLayout>
    <router-view v-else />
  </template>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import AppLayout from '@/layouts/AppLayout.vue'

const auth = useAuthStore()
const route = useRoute()

const isLoginRoute = computed(() => route.path === '/login')
</script>

<style>
.app-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--ss-bg-base);
}
</style>
