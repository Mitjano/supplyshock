<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="logo">SupplyShock</h1>
      <p class="subtitle">Global commodity supply chain monitoring</p>

      <div v-if="auth.loading" class="loading">Loading...</div>

      <template v-else-if="!auth.isAuthenticated">
        <button class="btn btn-primary" @click="auth.signIn()">Sign in</button>
        <button class="btn btn-secondary" @click="auth.signUp()">Create account</button>
      </template>

      <template v-else>
        <p class="welcome">Welcome, {{ auth.user?.name || auth.user?.email }}</p>
        <p class="plan-badge">{{ auth.plan }} plan</p>
        <button class="btn btn-secondary" @click="auth.signOut()">Sign out</button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/useAuthStore'

const auth = useAuthStore()
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #0f172a;
  color: #e2e8f0;
}

.login-card {
  text-align: center;
  max-width: 400px;
  padding: 3rem 2rem;
}

.logo {
  font-size: 2.5rem;
  background: linear-gradient(135deg, #3b82f6, #10b981);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #94a3b8;
  margin-bottom: 2rem;
}

.btn {
  display: block;
  width: 100%;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.5rem;
  font-size: 1rem;
  cursor: pointer;
  margin-bottom: 0.75rem;
  transition: opacity 0.2s;
}

.btn:hover {
  opacity: 0.9;
}

.btn-primary {
  background: linear-gradient(135deg, #3b82f6, #10b981);
  color: white;
}

.btn-secondary {
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #334155;
}

.welcome {
  font-size: 1.2rem;
  margin-bottom: 0.5rem;
}

.plan-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: #1e293b;
  border-radius: 1rem;
  font-size: 0.85rem;
  color: #10b981;
  text-transform: uppercase;
  margin-bottom: 1.5rem;
}

.loading {
  color: #64748b;
}
</style>
