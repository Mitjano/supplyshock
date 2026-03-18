<template>
  <div class="settings-view fade-in">
    <header class="settings-header">
      <h1>{{ t('settings.title') }}</h1>
      <p class="text-secondary">{{ t('settings.subtitle') }}</p>
    </header>

    <!-- Tab Navigation -->
    <nav class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <i :class="['pi', tab.icon]" />
        <span class="tab-label">{{ t(tab.labelKey) }}</span>
      </button>
    </nav>

    <!-- Tab Content -->
    <div class="tab-content">

      <!-- ==================== PROFILE TAB ==================== -->
      <section v-if="activeTab === 'profile'" class="tab-panel fade-in">
        <div class="profile-card ss-card">
          <div class="profile-top">
            <div class="avatar-wrapper">
              <img
                v-if="authStore.user?.avatar_url"
                :src="authStore.user.avatar_url"
                :alt="authStore.user.name ?? ''"
                class="avatar-img"
              />
              <div v-else class="avatar-initials">
                {{ userInitials }}
              </div>
            </div>
            <div class="profile-info">
              <div class="profile-name-row">
                <h2 class="profile-name">{{ authStore.user?.name || t('settings.profile.anonymous') }}</h2>
                <span :class="['plan-badge', `plan-${authStore.plan}`]">
                  {{ planLabel }}
                </span>
              </div>
              <p class="profile-email">{{ authStore.user?.email }}</p>
              <p class="profile-member-since">
                {{ t('settings.profile.memberSince') }}: {{ formattedMemberSince }}
              </p>
            </div>
          </div>
          <div class="profile-actions">
            <button class="ss-btn ss-btn-secondary" @click="openClerkProfile">
              <i class="pi pi-user-edit" />
              {{ t('settings.profile.manageAccount') }}
            </button>
          </div>
        </div>

        <!-- Danger Zone — Account Deletion -->
        <div class="danger-zone ss-card">
          <h3 class="section-title danger-title">
            <i class="pi pi-exclamation-triangle" />
            {{ t('settings.profile.deleteAccount') }}
          </h3>
          <p class="danger-desc">{{ t('settings.profile.deleteAccountDesc') }}</p>

          <!-- Confirmation dialog -->
          <div v-if="showDeleteConfirm" class="delete-confirm-box">
            <p class="delete-confirm-msg">{{ t('settings.profile.deleteConfirmMessage') }}</p>
            <div class="delete-confirm-actions">
              <button
                class="ss-btn ss-btn-danger"
                :disabled="deletingAccount"
                @click="confirmDeleteAccount"
              >
                <i :class="deletingAccount ? 'pi pi-spin pi-spinner' : 'pi pi-trash'" />
                {{ t('settings.profile.deleteConfirmButton') }}
              </button>
              <button
                class="ss-btn ss-btn-secondary"
                :disabled="deletingAccount"
                @click="showDeleteConfirm = false"
              >
                {{ t('settings.profile.deleteCancelButton') }}
              </button>
            </div>
          </div>

          <button
            v-else
            class="ss-btn ss-btn-danger-outline"
            @click="showDeleteConfirm = true"
          >
            <i class="pi pi-trash" />
            {{ t('settings.profile.deleteAccount') }}
          </button>
        </div>
      </section>

      <!-- ==================== BILLING TAB ==================== -->
      <section v-if="activeTab === 'billing'" class="tab-panel fade-in">
        <!-- Current Plan -->
        <div class="current-plan-card ss-card">
          <div class="current-plan-header">
            <div>
              <h3>{{ t('settings.billing.currentPlan') }}</h3>
              <span :class="['plan-badge plan-badge-lg', `plan-${authStore.plan}`]">
                {{ planLabel }}
              </span>
            </div>
            <button
              v-if="authStore.plan !== 'free'"
              class="ss-btn ss-btn-outline"
              @click="openBillingPortal"
              :disabled="billingLoading"
            >
              <i class="pi pi-credit-card" />
              {{ t('settings.billing.manageBilling') }}
            </button>
          </div>
        </div>

        <!-- Plan Comparison -->
        <div class="plans-grid">
          <div
            v-for="plan in plans"
            :key="plan.id"
            :class="['plan-card ss-card', { 'plan-current': authStore.plan === plan.id, 'plan-featured': plan.featured }]"
          >
            <div v-if="plan.featured" class="plan-featured-badge">
              {{ t('settings.billing.popular') }}
            </div>
            <h3 class="plan-name">{{ t(`settings.billing.plans.${plan.id}.name`) }}</h3>
            <div class="plan-price">
              <span v-if="plan.price === 0" class="price-free">{{ t('settings.billing.free') }}</span>
              <template v-else>
                <span class="price-amount">${{ plan.price }}</span>
                <span class="price-period">/{{ t('settings.billing.month') }}</span>
              </template>
            </div>
            <ul class="plan-features">
              <li v-for="(feature, idx) in plan.features" :key="idx">
                <i class="pi pi-check" />
                {{ t(feature) }}
              </li>
            </ul>
            <button
              v-if="authStore.plan === plan.id"
              class="ss-btn ss-btn-disabled plan-btn"
              disabled
            >
              {{ t('settings.billing.currentPlanLabel') }}
            </button>
            <button
              v-else-if="plan.price > 0"
              class="ss-btn ss-btn-primary plan-btn"
              :disabled="billingLoading"
              @click="startCheckout(plan.id)"
            >
              {{ t('settings.billing.upgrade') }}
            </button>
            <div v-else class="plan-btn-spacer" />
          </div>
        </div>
      </section>

      <!-- ==================== NOTIFICATIONS TAB ==================== -->
      <section v-if="activeTab === 'notifications'" class="tab-panel fade-in">
        <!-- Existing Subscriptions -->
        <div class="subscriptions-section">
          <h3 class="section-title">{{ t('settings.notifications.activeSubscriptions') }}</h3>

          <div v-if="subsLoading" class="subs-loading">
            <i class="pi pi-spin pi-spinner" />
            {{ t('common.loading') }}
          </div>

          <div v-else-if="!subscriptions.length" class="subs-empty ss-card">
            <i class="pi pi-bell-slash" />
            <p>{{ t('settings.notifications.noSubscriptions') }}</p>
          </div>

          <div v-else class="subs-list">
            <div v-for="sub in subscriptions" :key="sub.id" class="sub-item ss-card">
              <div class="sub-info">
                <div class="sub-tags">
                  <span v-if="sub.commodity" class="sub-tag tag-commodity">{{ formatCommodityName(sub.commodity) }}</span>
                  <span v-if="sub.alert_type" class="sub-tag tag-type">{{ sub.alert_type }}</span>
                  <span :class="['sub-tag', `tag-sev-${sub.min_severity}`]">
                    {{ t(`settings.notifications.severity.${sub.min_severity}`) }}+
                  </span>
                </div>
                <div class="sub-channels">
                  <span v-if="sub.notify_email" class="channel-tag">
                    <i class="pi pi-envelope" /> {{ t('settings.notifications.email') }}
                  </span>
                  <span v-if="sub.notify_webhook" class="channel-tag">
                    <i class="pi pi-link" /> {{ t('settings.notifications.webhook') }}
                  </span>
                </div>
              </div>
              <button
                class="ss-btn ss-btn-danger-ghost btn-sm"
                @click="deleteSubscription(sub.id)"
                :disabled="deletingSub === sub.id"
              >
                <i :class="deletingSub === sub.id ? 'pi pi-spin pi-spinner' : 'pi pi-trash'" />
              </button>
            </div>
          </div>
        </div>

        <!-- Add New Subscription -->
        <div class="new-sub-section ss-card">
          <h3 class="section-title">{{ t('settings.notifications.addNew') }}</h3>
          <div class="new-sub-form">
            <div class="form-row">
              <div class="form-group">
                <label>{{ t('settings.notifications.commodityLabel') }}</label>
                <select v-model="newSub.commodity" class="ss-input">
                  <option value="">{{ t('settings.notifications.anyCommodity') }}</option>
                  <option v-for="c in commodityOptions" :key="c" :value="c">{{ formatCommodityName(c) }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>{{ t('settings.notifications.alertTypeLabel') }}</label>
                <select v-model="newSub.alert_type" class="ss-input">
                  <option value="">{{ t('settings.notifications.anyType') }}</option>
                  <option v-for="at in alertTypeOptions" :key="at.value" :value="at.value">{{ at.label }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>{{ t('settings.notifications.minSeverityLabel') }}</label>
                <select v-model="newSub.min_severity" class="ss-input">
                  <option value="info">{{ t('settings.notifications.severity.info') }}</option>
                  <option value="warning">{{ t('settings.notifications.severity.warning') }}</option>
                  <option value="critical">{{ t('settings.notifications.severity.critical') }}</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group toggle-group">
                <label class="toggle-label">
                  <input type="checkbox" v-model="newSub.notify_email" class="ss-toggle" />
                  <span class="toggle-switch" />
                  <span>{{ t('settings.notifications.emailNotify') }}</span>
                </label>
              </div>
              <div class="form-group toggle-group">
                <label class="toggle-label">
                  <input type="checkbox" v-model="newSub.notify_webhook" class="ss-toggle" />
                  <span class="toggle-switch" />
                  <span>{{ t('settings.notifications.webhookNotify') }}</span>
                </label>
              </div>
              <div v-if="newSub.notify_webhook" class="form-group form-group-wide">
                <label>{{ t('settings.notifications.webhookUrl') }}</label>
                <input
                  type="url"
                  v-model="newSub.webhook_url"
                  class="ss-input"
                  placeholder="https://..."
                />
              </div>
            </div>
            <div class="form-actions">
              <button
                class="ss-btn ss-btn-primary"
                @click="createSubscription"
                :disabled="creatingSub"
              >
                <i :class="creatingSub ? 'pi pi-spin pi-spinner' : 'pi pi-plus'" />
                {{ t('settings.notifications.addSubscription') }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ==================== API KEYS TAB ==================== -->
      <section v-if="activeTab === 'apikeys'" class="tab-panel fade-in">
        <div class="api-card ss-card">
          <div class="api-coming-soon">
            <div class="api-icon-wrap">
              <i class="pi pi-code" />
            </div>
            <h3>{{ t('settings.apiKeys.title') }}</h3>
            <p class="text-secondary">{{ t('settings.apiKeys.description') }}</p>

            <div v-if="!authStore.isPro" class="api-upgrade-notice">
              <i class="pi pi-lock" />
              <span>{{ t('settings.apiKeys.proRequired') }}</span>
            </div>

            <div class="api-features">
              <div v-for="(feature, idx) in apiFeatures" :key="idx" class="api-feature">
                <i class="pi pi-check-circle" />
                <span>{{ t(feature) }}</span>
              </div>
            </div>

            <div class="api-example">
              <h4>{{ t('settings.apiKeys.exampleTitle') }}</h4>
              <pre class="code-block"><code>curl -H "Authorization: Bearer YOUR_API_KEY" \
  {{ apiBaseUrl }}/api/v1/commodities/prices</code></pre>
            </div>

            <span class="coming-soon-badge">
              <i class="pi pi-clock" />
              {{ t('common.comingSoon') }}
            </span>
          </div>
        </div>
      </section>

      <!-- ==================== PREFERENCES TAB ==================== -->
      <section v-if="activeTab === 'preferences'" class="tab-panel fade-in">
        <div class="prefs-card ss-card">
          <h3 class="section-title">{{ t('settings.preferences.title') }}</h3>

          <!-- Language -->
          <div class="pref-item">
            <div class="pref-info">
              <i class="pi pi-globe" />
              <div>
                <span class="pref-label">{{ t('settings.preferences.language') }}</span>
                <span class="pref-desc">{{ t('settings.preferences.languageDesc') }}</span>
              </div>
            </div>
            <select v-model="selectedLocale" class="ss-input ss-input-sm" @change="changeLocale">
              <option value="en">English</option>
              <option value="pl">Polski</option>
            </select>
          </div>

          <!-- Theme -->
          <div class="pref-item">
            <div class="pref-info">
              <i class="pi pi-moon" />
              <div>
                <span class="pref-label">{{ t('settings.preferences.theme') }}</span>
                <span class="pref-desc">{{ t('settings.preferences.themeDesc') }}</span>
              </div>
            </div>
            <div class="theme-selector">
              <button
                :class="['theme-btn', { active: theme === 'dark' }]"
                @click="theme = 'dark'"
              >
                <i class="pi pi-moon" />
                {{ t('settings.preferences.dark') }}
              </button>
              <button
                :class="['theme-btn', { active: theme === 'light', disabled: true }]"
                disabled
                :title="t('common.comingSoon')"
              >
                <i class="pi pi-sun" />
                {{ t('settings.preferences.light') }}
              </button>
            </div>
          </div>

          <!-- Refresh Interval -->
          <div class="pref-item">
            <div class="pref-info">
              <i class="pi pi-sync" />
              <div>
                <span class="pref-label">{{ t('settings.preferences.refreshInterval') }}</span>
                <span class="pref-desc">{{ t('settings.preferences.refreshDesc') }}</span>
              </div>
            </div>
            <select v-model="refreshInterval" class="ss-input ss-input-sm">
              <option value="15">15s</option>
              <option value="30">30s</option>
              <option value="60">60s</option>
              <option value="300">5min</option>
            </select>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { useApi } from '@/composables/useApi'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const api = useApi()

// ────────────── Tab State ──────────────
const activeTab = ref('profile')

const tabs = [
  { id: 'profile', icon: 'pi-user', labelKey: 'settings.tabs.profile' },
  { id: 'billing', icon: 'pi-credit-card', labelKey: 'settings.tabs.billing' },
  { id: 'notifications', icon: 'pi-bell', labelKey: 'settings.tabs.notifications' },
  { id: 'apikeys', icon: 'pi-code', labelKey: 'settings.tabs.apiKeys' },
  { id: 'preferences', icon: 'pi-cog', labelKey: 'settings.tabs.preferences' },
]

// ────────────── Profile ──────────────
const userInitials = computed(() => {
  const name = authStore.user?.name || authStore.user?.email || '?'
  const parts = name.split(/[\s@]+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.substring(0, 2).toUpperCase()
})

const planLabel = computed(() => {
  const p = authStore.plan
  return p.charAt(0).toUpperCase() + p.slice(1)
})

const formattedMemberSince = computed(() => {
  if (!authStore.user?.created_at) return '—'
  return new Date(authStore.user.created_at).toLocaleDateString(locale.value, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
})

function openClerkProfile() {
  authStore.clerk?.openUserProfile()
}

// ────────────── Account Deletion ──────────────
const showDeleteConfirm = ref(false)
const deletingAccount = ref(false)

async function confirmDeleteAccount() {
  deletingAccount.value = true
  try {
    await api.del('/auth/me')
    // Sign out from Clerk and redirect
    await authStore.clerk?.signOut()
    router.push('/')
  } catch (e) {
    console.error('Account deletion failed:', e)
    alert(t('settings.profile.deleteError'))
  } finally {
    deletingAccount.value = false
    showDeleteConfirm.value = false
  }
}

// ────────────── Billing ──────────────
const billingLoading = ref(false)

const plans = [
  {
    id: 'free',
    price: 0,
    featured: false,
    features: [
      'settings.billing.plans.free.f1',
      'settings.billing.plans.free.f2',
      'settings.billing.plans.free.f3',
    ],
  },
  {
    id: 'pro',
    price: 49,
    featured: true,
    features: [
      'settings.billing.plans.pro.f1',
      'settings.billing.plans.pro.f2',
      'settings.billing.plans.pro.f3',
      'settings.billing.plans.pro.f4',
    ],
  },
  {
    id: 'business',
    price: 199,
    featured: false,
    features: [
      'settings.billing.plans.business.f1',
      'settings.billing.plans.business.f2',
      'settings.billing.plans.business.f3',
      'settings.billing.plans.business.f4',
    ],
  },
]

async function startCheckout(planId: string) {
  billingLoading.value = true
  try {
    const res = await api.post<{ data: { checkout_url: string } }>('/billing/checkout', {
      plan: planId,
    })
    window.location.href = res.data.checkout_url
  } catch (e) {
    console.error('Checkout error:', e)
    billingLoading.value = false
  }
}

async function openBillingPortal() {
  billingLoading.value = true
  try {
    const res = await api.post<{ data: { portal_url: string } }>('/billing/portal')
    window.location.href = res.data.portal_url
  } catch (e) {
    console.error('Portal error:', e)
    billingLoading.value = false
  }
}

// ────────────── Notifications ──────────────
interface Subscription {
  id: string
  commodity: string | null
  alert_type: string | null
  min_severity: string
  notify_email: boolean
  notify_webhook: boolean
  webhook_url: string | null
  created_at: string
}

const subscriptions = ref<Subscription[]>([])
const subsLoading = ref(false)
const creatingSub = ref(false)
const deletingSub = ref<string | null>(null)

const newSub = reactive({
  commodity: '',
  alert_type: '',
  min_severity: 'warning',
  notify_email: true,
  notify_webhook: false,
  webhook_url: '',
})

const commodityOptions = [
  'crude_oil', 'natural_gas', 'coal', 'iron_ore', 'copper',
  'aluminum', 'gold', 'wheat', 'corn', 'soybeans', 'lng',
]

const alertTypeOptions = [
  { value: 'ais_anomaly', label: 'AIS Anomaly' },
  { value: 'price_move', label: 'Price Move' },
  { value: 'news', label: 'News' },
  { value: 'port_congestion', label: 'Port Congestion' },
  { value: 'geopolitical', label: 'Geopolitical' },
]

function formatCommodityName(commodity: string): string {
  return commodity.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

async function fetchSubscriptions() {
  subsLoading.value = true
  try {
    const res = await api.get<{ data: Subscription[] }>('/alert-subscriptions')
    subscriptions.value = res.data
  } catch (e) {
    console.error('Failed to load subscriptions:', e)
  } finally {
    subsLoading.value = false
  }
}

async function createSubscription() {
  creatingSub.value = true
  try {
    await api.post('/alert-subscriptions', {
      commodity: newSub.commodity || null,
      alert_type: newSub.alert_type || null,
      min_severity: newSub.min_severity,
      notify_email: newSub.notify_email,
      notify_webhook: newSub.notify_webhook,
      webhook_url: newSub.notify_webhook && newSub.webhook_url ? newSub.webhook_url : null,
    })
    // Reset form
    newSub.commodity = ''
    newSub.alert_type = ''
    newSub.min_severity = 'warning'
    newSub.notify_email = true
    newSub.notify_webhook = false
    newSub.webhook_url = ''
    await fetchSubscriptions()
  } catch (e) {
    console.error('Failed to create subscription:', e)
  } finally {
    creatingSub.value = false
  }
}

async function deleteSubscription(id: string) {
  deletingSub.value = id
  try {
    await api.del(`/alert-subscriptions/${id}`)
    subscriptions.value = subscriptions.value.filter(s => s.id !== id)
  } catch (e) {
    console.error('Failed to delete subscription:', e)
  } finally {
    deletingSub.value = null
  }
}

// ────────────── API Keys ──────────────
const apiBaseUrl = import.meta.env.VITE_API_URL || 'https://api.supplyshock.io'

const apiFeatures = [
  'settings.apiKeys.features.f1',
  'settings.apiKeys.features.f2',
  'settings.apiKeys.features.f3',
  'settings.apiKeys.features.f4',
]

// ────────────── Preferences ──────────────
const selectedLocale = ref(locale.value)
const theme = ref('dark')
const refreshInterval = ref('60')

function changeLocale() {
  const newLocale = selectedLocale.value
  localStorage.setItem('ss-locale', newLocale)

  // Navigate to equivalent path with/without /en prefix
  const currentPath = route.path
  let basePath = currentPath.startsWith('/en/') ? currentPath.slice(3) : currentPath === '/en' ? '/' : currentPath
  const newPath = newLocale === 'en' ? `/en${basePath === '/' ? '' : basePath}` : basePath
  router.push(newPath)
}

// ────────────── Init ──────────────
onMounted(() => {
  // Sync locale selector with current URL-derived locale
  selectedLocale.value = locale.value

  // Restore saved refresh interval
  const savedInterval = localStorage.getItem('ss-refresh-interval')
  if (savedInterval) refreshInterval.value = savedInterval

  // Load subscriptions if authenticated
  if (authStore.isAuthenticated) {
    fetchSubscriptions()
  }
})
</script>

<style scoped>
.settings-view {
  padding: 1.5rem 2rem;
  max-width: 1100px;
  margin: 0 auto;
  min-height: 100vh;
}

/* ── Header ── */
.settings-header {
  margin-bottom: 1.5rem;
}

.settings-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

/* ── Tabs Navigation ── */
.settings-tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--ss-border-light);
  margin-bottom: 1.5rem;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.tab-btn {
  background: transparent;
  border: none;
  color: var(--ss-text-muted);
  padding: 0.75rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
  border-bottom: 2px solid transparent;
  transition: all var(--ss-transition-fast);
  position: relative;
  bottom: -1px;
}

.tab-btn:hover {
  color: var(--ss-text-secondary);
}

.tab-btn.active {
  color: var(--ss-accent);
  border-bottom-color: var(--ss-accent);
}

/* ── Shared card / btn styles ── */
.ss-card {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1.5rem;
}

.ss-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1.25rem;
  border-radius: var(--ss-radius);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--ss-transition-fast);
  white-space: nowrap;
}

.ss-btn-primary {
  background: var(--ss-accent);
  color: #fff;
  border-color: var(--ss-accent);
}

.ss-btn-primary:hover:not(:disabled) {
  background: var(--ss-accent-light);
  border-color: var(--ss-accent-light);
}

.ss-btn-secondary {
  background: var(--ss-bg-elevated);
  color: var(--ss-text-primary);
  border-color: var(--ss-border-light);
}

.ss-btn-secondary:hover:not(:disabled) {
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

.ss-btn-outline {
  background: transparent;
  color: var(--ss-text-secondary);
  border-color: var(--ss-border-light);
}

.ss-btn-outline:hover:not(:disabled) {
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

.ss-btn-disabled {
  background: var(--ss-bg-elevated);
  color: var(--ss-text-muted);
  border-color: var(--ss-border-light);
  cursor: not-allowed;
  opacity: 0.6;
}

.ss-btn-danger-ghost {
  background: transparent;
  color: var(--ss-danger);
  border-color: transparent;
}

.ss-btn-danger-ghost:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
}

.btn-sm {
  padding: 0.4rem 0.6rem;
  font-size: 0.8rem;
}

.ss-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ss-input {
  background: var(--ss-bg-base);
  border: 1px solid var(--ss-border-light);
  color: var(--ss-text-primary);
  padding: 0.5rem 0.75rem;
  border-radius: var(--ss-radius-sm);
  font-size: 0.875rem;
  outline: none;
  transition: border-color var(--ss-transition-fast);
  width: 100%;
}

.ss-input:focus {
  border-color: var(--ss-accent);
}

.ss-input-sm {
  width: auto;
  min-width: 120px;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 1rem;
  color: var(--ss-text-primary);
}

/* ── Profile Tab ── */
.profile-card {
  max-width: 700px;
}

.profile-top {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.avatar-wrapper {
  flex-shrink: 0;
}

.avatar-img {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid var(--ss-border-light);
}

.avatar-initials {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--ss-accent-dim);
  color: var(--ss-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 700;
  border: 3px solid var(--ss-border-light);
}

.profile-info {
  flex: 1;
  min-width: 0;
}

.profile-name-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}

.profile-name {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0;
}

.plan-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.plan-badge-lg {
  padding: 0.25rem 0.8rem;
  font-size: 0.8rem;
}

.plan-free { background: rgba(100, 116, 139, 0.2); color: #94a3b8; }
.plan-pro { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.plan-business { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
.plan-enterprise { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }

.profile-email {
  color: var(--ss-text-secondary);
  font-size: 0.9rem;
  margin: 0 0 0.25rem;
}

.profile-member-since {
  color: var(--ss-text-muted);
  font-size: 0.8rem;
  margin: 0;
}

.profile-actions {
  border-top: 1px solid var(--ss-border-light);
  padding-top: 1.25rem;
}

/* ── Danger Zone ── */
.danger-zone {
  margin-top: 1.5rem;
  max-width: 700px;
  border-color: rgba(239, 68, 68, 0.3);
}

.danger-title {
  color: var(--ss-danger, #ef4444);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.danger-desc {
  color: var(--ss-text-muted);
  font-size: 0.85rem;
  margin: 0 0 1rem;
}

.delete-confirm-box {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--ss-radius);
  padding: 1.25rem;
}

.delete-confirm-msg {
  color: var(--ss-text-secondary);
  font-size: 0.875rem;
  margin: 0 0 1rem;
  line-height: 1.5;
}

.delete-confirm-actions {
  display: flex;
  gap: 0.75rem;
}

.ss-btn-danger {
  background: #ef4444;
  color: #fff;
  border-color: #ef4444;
}

.ss-btn-danger:hover:not(:disabled) {
  background: #dc2626;
  border-color: #dc2626;
}

.ss-btn-danger-outline {
  background: transparent;
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.4);
}

.ss-btn-danger-outline:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
}

/* ── Billing Tab ── */
.current-plan-card {
  margin-bottom: 1.5rem;
}

.current-plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.current-plan-header h3 {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ss-text-muted);
  margin: 0 0 0.5rem;
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
}

.plan-card {
  display: flex;
  flex-direction: column;
  position: relative;
  transition: border-color var(--ss-transition-fast), transform var(--ss-transition-fast);
}

.plan-card:hover {
  border-color: var(--ss-accent-dim);
}

.plan-current {
  border-color: var(--ss-accent);
}

.plan-featured {
  border-color: #3b82f6;
}

.plan-featured-badge {
  position: absolute;
  top: -10px;
  right: 16px;
  background: #3b82f6;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.15rem 0.6rem;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.plan-name {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.plan-price {
  margin-bottom: 1.25rem;
}

.price-free {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--ss-text-primary);
}

.price-amount {
  font-size: 2rem;
  font-weight: 800;
  color: var(--ss-text-primary);
}

.price-period {
  font-size: 0.9rem;
  color: var(--ss-text-muted);
}

.plan-features {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  flex: 1;
}

.plan-features li {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--ss-text-secondary);
  padding: 0.35rem 0;
}

.plan-features li .pi-check {
  color: var(--ss-accent);
  font-size: 0.8rem;
  margin-top: 0.15rem;
  flex-shrink: 0;
}

.plan-btn {
  width: 100%;
  justify-content: center;
}

.plan-btn-spacer {
  height: 42px;
}

/* ── Notifications Tab ── */
.subscriptions-section {
  margin-bottom: 1.5rem;
}

.subs-loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--ss-text-muted);
  padding: 2rem;
  justify-content: center;
}

.subs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2.5rem;
  color: var(--ss-text-muted);
  text-align: center;
}

.subs-empty .pi {
  font-size: 2rem;
  opacity: 0.5;
}

.subs-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sub-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  gap: 1rem;
}

.sub-info {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.sub-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.sub-tag {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.tag-commodity { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.tag-type { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.tag-sev-info { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.tag-sev-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.tag-sev-critical { background: rgba(239, 68, 68, 0.15); color: #f87171; }

.sub-channels {
  display: flex;
  gap: 0.5rem;
}

.channel-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: var(--ss-text-muted);
}

/* New subscription form */
.new-sub-section {
  /* uses ss-card */
}

.new-sub-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1;
  min-width: 180px;
}

.form-group label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ss-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.form-group-wide {
  flex: 2;
  min-width: 280px;
}

/* Toggle switch */
.toggle-group {
  min-width: auto;
  flex: 0 0 auto;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--ss-text-secondary);
  padding-top: 1.2rem;
}

.ss-toggle {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-switch {
  position: relative;
  width: 40px;
  height: 22px;
  background: var(--ss-bg-elevated);
  border-radius: 11px;
  transition: background var(--ss-transition-fast);
  flex-shrink: 0;
}

.toggle-switch::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  background: var(--ss-text-muted);
  border-radius: 50%;
  transition: all var(--ss-transition-fast);
}

.ss-toggle:checked + .toggle-switch {
  background: var(--ss-accent);
}

.ss-toggle:checked + .toggle-switch::after {
  left: 21px;
  background: #fff;
}

.form-actions {
  padding-top: 0.5rem;
}

/* ── API Keys Tab ── */
.api-coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem 1rem;
  max-width: 600px;
  margin: 0 auto;
}

.api-icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: var(--ss-accent-dim);
  color: var(--ss-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.75rem;
  margin-bottom: 1rem;
}

.api-coming-soon h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.api-upgrade-notice {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(245, 158, 11, 0.1);
  color: var(--ss-warning);
  padding: 0.5rem 1rem;
  border-radius: var(--ss-radius);
  font-size: 0.85rem;
  margin: 1rem 0;
}

.api-features {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 1.5rem 0;
  text-align: left;
  width: 100%;
  max-width: 400px;
}

.api-feature {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--ss-text-secondary);
}

.api-feature .pi-check-circle {
  color: var(--ss-accent);
  font-size: 0.85rem;
}

.api-example {
  width: 100%;
  margin-top: 1.5rem;
  text-align: left;
}

.api-example h4 {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--ss-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 0.5rem;
}

.code-block {
  background: var(--ss-bg-base);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  padding: 1rem 1.25rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  color: var(--ss-accent-light);
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}

.coming-soon-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 1.5rem;
  background: var(--ss-bg-elevated);
  color: var(--ss-text-muted);
  padding: 0.4rem 1rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
}

/* ── Preferences Tab ── */
.prefs-card {
  max-width: 700px;
}

.pref-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid var(--ss-border-light);
  gap: 1.5rem;
}

.pref-item:last-child {
  border-bottom: none;
}

.pref-info {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.pref-info > .pi {
  color: var(--ss-text-muted);
  font-size: 1.1rem;
  margin-top: 0.1rem;
}

.pref-label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ss-text-primary);
  margin-bottom: 0.15rem;
}

.pref-desc {
  display: block;
  font-size: 0.8rem;
  color: var(--ss-text-muted);
}

.theme-selector {
  display: flex;
  gap: 0.25rem;
}

.theme-btn {
  background: var(--ss-bg-base);
  border: 1px solid var(--ss-border-light);
  color: var(--ss-text-muted);
  padding: 0.4rem 0.75rem;
  border-radius: var(--ss-radius-sm);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  transition: all var(--ss-transition-fast);
}

.theme-btn:hover:not(:disabled) {
  border-color: var(--ss-accent);
  color: var(--ss-text-primary);
}

.theme-btn.active {
  background: var(--ss-accent-dim);
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

.theme-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .settings-view {
    padding: 1rem;
  }

  .settings-tabs {
    gap: 0;
  }

  .tab-btn {
    padding: 0.6rem 0.75rem;
    font-size: 0.8rem;
  }

  .tab-label {
    display: none;
  }

  .tab-btn .pi {
    font-size: 1.1rem;
  }

  .profile-top {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .profile-name-row {
    justify-content: center;
    flex-wrap: wrap;
  }

  .plans-grid {
    grid-template-columns: 1fr;
  }

  .current-plan-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .form-row {
    flex-direction: column;
  }

  .form-group {
    min-width: 0;
  }

  .pref-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .sub-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
