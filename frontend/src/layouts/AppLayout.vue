<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': collapsed }">
    <!-- Mobile overlay -->
    <div
      v-if="mobileOpen"
      class="sidebar-overlay"
      @click="mobileOpen = false"
    />

    <!-- Sidebar -->
    <aside
      class="sidebar"
      :class="{ open: mobileOpen }"
    >
      <!-- Brand -->
      <div class="sidebar-brand" @click="router.push(localePath('/'))">
        <i class="pi pi-bolt brand-icon" />
        <transition name="fade-text">
          <span v-if="!collapsed" class="brand-name">SupplyShock</span>
        </transition>
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav">
        <div
          v-for="section in navSections"
          :key="section.titleKey"
          class="nav-section"
        >
          <span v-if="!collapsed" class="nav-section-title">{{ t(section.titleKey) }}</span>
          <router-link
            v-for="item in section.items"
            :key="item.key"
            :to="item.route"
            class="nav-item"
            :class="{ active: isActive(item.route) }"
            @click="mobileOpen = false"
          >
            <i :class="['pi', item.icon]" />
            <transition name="fade-text">
              <span v-if="!collapsed" class="nav-label">{{ item.label() }}</span>
            </transition>
            <span
              v-if="item.badge && item.badge.value > 0 && !collapsed"
              class="nav-badge"
            >
              {{ item.badge.value }}
            </span>
          </router-link>
        </div>
      </nav>

      <!-- Bottom actions -->
      <div class="sidebar-bottom">
        <router-link
          :to="localePath('/settings')"
          class="nav-item"
          :class="{ active: isActive('/settings') }"
          @click="mobileOpen = false"
        >
          <i class="pi pi-cog" />
          <transition name="fade-text">
            <span v-if="!collapsed" class="nav-label">{{ t('nav.settings') }}</span>
          </transition>
        </router-link>

        <!-- User info -->
        <div v-if="auth.user" class="sidebar-user">
          <Avatar
            :label="userInitials"
            :image="auth.user.avatar_url ?? undefined"
            shape="circle"
            class="user-avatar"
          />
          <transition name="fade-text">
            <div v-if="!collapsed" class="user-info">
              <span class="user-name">{{ auth.user.name || auth.user.email }}</span>
              <span class="user-plan ss-badge ss-badge--accent">{{ auth.plan }}</span>
            </div>
          </transition>
        </div>

        <!-- Collapse toggle (desktop only) -->
        <button class="collapse-btn" @click="collapsed = !collapsed">
          <i :class="['pi', collapsed ? 'pi-angle-right' : 'pi-angle-left']" />
          <transition name="fade-text">
            <span v-if="!collapsed" class="nav-label">{{ t('layout.collapse') }}</span>
          </transition>
        </button>
      </div>
    </aside>

    <!-- Main area -->
    <div class="main-area">
      <!-- Top bar -->
      <header class="topbar">
        <div class="topbar-left">
          <button class="mobile-menu-btn" @click="mobileOpen = !mobileOpen">
            <i class="pi pi-bars" />
          </button>
          <nav class="breadcrumb">
            <span class="breadcrumb-item text-muted">SupplyShock</span>
            <i class="pi pi-angle-right breadcrumb-sep" />
            <span class="breadcrumb-item">{{ currentPageTitle }}</span>
          </nav>
        </div>

        <div class="topbar-right">
          <button class="topbar-search" @click="globalSearchRef?.open()">
            <i class="pi pi-search" />
            <span class="search-placeholder">{{ t('common.search') }}</span>
            <kbd class="search-shortcut">{{ isMac ? '⌘K' : 'Ctrl+K' }}</kbd>
          </button>

          <button class="topbar-icon-btn" @click="router.push(localePath('/alerts'))">
            <i class="pi pi-bell" />
            <span v-if="alertCount > 0" class="topbar-badge">{{ alertCount }}</span>
          </button>

          <button class="topbar-icon-btn" @click="showUserMenu = !showUserMenu">
            <Avatar
              :label="userInitials"
              :image="auth.user?.avatar_url ?? undefined"
              shape="circle"
              size="small"
            />
          </button>

          <!-- User dropdown -->
          <div v-if="showUserMenu" class="user-dropdown" @mouseleave="showUserMenu = false">
            <div class="dropdown-header">
              <strong>{{ auth.user?.name || auth.user?.email }}</strong>
              <span class="text-muted">{{ auth.plan }} plan</span>
            </div>
            <div class="dropdown-divider" />
            <button class="dropdown-item" @click="router.push(localePath('/settings')); showUserMenu = false">
              <i class="pi pi-cog" /> {{ t('nav.settings') }}
            </button>
            <button class="dropdown-item dropdown-item--danger" @click="auth.signOut()">
              <i class="pi pi-sign-out" /> {{ t('layout.signOut') }}
            </button>
          </div>
        </div>
      </header>

      <!-- Page content -->
      <main class="page-content">
        <slot />
      </main>
    </div>

    <!-- Global search modal -->
    <GlobalSearch ref="globalSearchRef" />

    <!-- AI Chat panel -->
    <ChatPanel />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/useAuthStore'
import { useLocalePath } from '@/composables/useLocalePath'
import GlobalSearch from '@/components/ui/GlobalSearch.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import Avatar from 'primevue/avatar'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { localePath } = useLocalePath()

const collapsed = ref(false)
const mobileOpen = ref(false)
const showUserMenu = ref(false)
const alertCount = ref(3) // TODO: fetch from API
const globalSearchRef = ref<InstanceType<typeof GlobalSearch> | null>(null)
const isMac = navigator.platform.toUpperCase().includes('MAC')

const userInitials = computed(() => {
  const name = auth.user?.name || auth.user?.email || '?'
  return name.substring(0, 2).toUpperCase()
})

/** Strip locale prefix from route.path for matching */
const cleanPath = computed(() => {
  const p = route.path
  if (p.startsWith('/en/')) return p.slice(3)
  if (p === '/en') return '/'
  return p
})

const currentPageTitle = computed(() => {
  const map: Record<string, string> = {
    '/': t('nav.home'),
    '/map': t('nav.map'),
    '/commodities': t('nav.commodities'),
    '/bottlenecks': t('nav.bottlenecks'),
    '/alerts': t('nav.alerts'),
    '/simulations': t('nav.simulations'),
    '/reports': t('nav.reports'),
    '/settings': t('nav.settings'),
    '/analytics': t('nav.analytics'),
    '/fleet': t('nav.fleet'),
    '/macro': t('nav.macro'),
    '/emissions': t('nav.emissions'),
  }
  return map[cleanPath.value] || 'Page'
})

function isActive(path: string): boolean {
  if (path === '/') return cleanPath.value === '/'
  return cleanPath.value.startsWith(path)
}

const navSections = computed(() => [
  {
    titleKey: 'layout.overview',
    items: [
      { key: 'home', icon: 'pi-home', route: localePath('/'), label: () => t('nav.home') },
      { key: 'map', icon: 'pi-map', route: localePath('/map'), label: () => t('nav.map') },
    ]
  },
  {
    titleKey: 'layout.markets',
    items: [
      { key: 'commodities', icon: 'pi-chart-line', route: localePath('/commodities'), label: () => t('nav.commodities') },
      { key: 'analytics', icon: 'pi-chart-bar', route: localePath('/analytics'), label: () => t('nav.analytics') },
      { key: 'macro', icon: 'pi-globe', route: localePath('/macro'), label: () => t('nav.macro') },
    ]
  },
  {
    titleKey: 'layout.intelligence',
    items: [
      { key: 'alerts', icon: 'pi-bell', route: localePath('/alerts'), label: () => t('nav.alerts'), badge: alertCount },
      { key: 'bottlenecks', icon: 'pi-exclamation-triangle', route: localePath('/bottlenecks'), label: () => t('nav.bottlenecks') },
      { key: 'compliance', icon: 'pi-shield', route: localePath('/compliance'), label: () => t('nav.compliance') },
      { key: 'fleet', icon: 'pi-truck', route: localePath('/fleet'), label: () => t('nav.fleet') },
      { key: 'emissions', icon: 'pi-cloud', route: localePath('/emissions'), label: () => t('nav.emissions') },
    ]
  },
  {
    titleKey: 'layout.tools',
    items: [
      { key: 'simulations', icon: 'pi-play', route: localePath('/simulations'), label: () => t('nav.simulations') },
      { key: 'reports', icon: 'pi-file', route: localePath('/reports'), label: () => t('nav.reports') },
    ]
  }
])
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* ── Sidebar ── */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--ss-sidebar-width);
  background: var(--ss-bg-surface);
  border-right: 1px solid var(--ss-border-light);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width var(--ss-transition);
  overflow-x: hidden;
}

.sidebar-collapsed .sidebar {
  width: var(--ss-sidebar-collapsed);
}

/* Brand */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1rem;
  cursor: pointer;
  border-bottom: 1px solid var(--ss-border-light);
  min-height: 64px;
}

.brand-icon {
  font-size: 1.5rem;
  color: var(--ss-accent);
  flex-shrink: 0;
  width: 40px;
  text-align: center;
}

.brand-name {
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--ss-accent), #3b82f6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  white-space: nowrap;
}

/* Navigation */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0;
}

.nav-section {
  margin-bottom: 0.5rem;
}

.nav-section-title {
  display: block;
  padding: 0.5rem 1.25rem 0.25rem;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ss-text-muted);
  white-space: nowrap;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  margin: 0.1rem 0.5rem;
  border-radius: var(--ss-radius);
  color: var(--ss-text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
  text-decoration: none;
  white-space: nowrap;
  position: relative;
}

.nav-item i {
  font-size: 1.1rem;
  width: 40px;
  text-align: center;
  flex-shrink: 0;
}

.nav-item:hover {
  background: var(--ss-accent-dim);
  color: var(--ss-text-primary);
}

.nav-item.active {
  background: var(--ss-accent-dim);
  color: var(--ss-accent);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: -0.5rem;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: var(--ss-accent);
  border-radius: 0 3px 3px 0;
}

.nav-badge {
  margin-left: auto;
  background: var(--ss-danger);
  color: white;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  min-width: 18px;
  text-align: center;
}

/* Sidebar bottom */
.sidebar-bottom {
  border-top: 1px solid var(--ss-border-light);
  padding: 0.5rem 0;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
}

.user-avatar {
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  white-space: nowrap;
}

.user-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--ss-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-plan {
  font-size: 0.65rem;
  margin-top: 0.15rem;
  width: fit-content;
}

.collapse-btn {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.6rem 1rem;
  margin: 0.1rem 0;
  background: none;
  border: none;
  color: var(--ss-text-muted);
  font-size: 0.875rem;
  cursor: pointer;
  transition: color var(--ss-transition-fast);
}

.collapse-btn i {
  width: 40px;
  text-align: center;
  font-size: 1.1rem;
  flex-shrink: 0;
}

.collapse-btn:hover {
  color: var(--ss-text-primary);
}

/* ── Main area ── */
.main-area {
  flex: 1;
  margin-left: var(--ss-sidebar-width);
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  transition: margin-left var(--ss-transition);
}

.sidebar-collapsed .main-area {
  margin-left: var(--ss-sidebar-collapsed);
}

/* ── Topbar ── */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  height: 56px;
  background: var(--ss-bg-surface);
  border-bottom: 1px solid var(--ss-border-light);
  position: sticky;
  top: 0;
  z-index: 50;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.mobile-menu-btn {
  display: none;
  background: none;
  border: none;
  color: var(--ss-text-secondary);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
}

.breadcrumb-sep {
  font-size: 0.75rem;
  color: var(--ss-text-muted);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  position: relative;
}

.topbar-search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--ss-bg-base);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  padding: 0.35rem 0.75rem;
  cursor: pointer;
  transition: border-color var(--ss-transition-fast);
  font-size: 0.85rem;
  color: var(--ss-text-muted);
  min-width: 200px;
}

.topbar-search:hover {
  border-color: var(--ss-accent);
}

.topbar-search i {
  font-size: 0.85rem;
}

.search-placeholder {
  flex: 1;
}

.search-shortcut {
  background: var(--ss-bg-elevated);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.65rem;
  border: 1px solid var(--ss-border-light);
  font-family: inherit;
}

.topbar-icon-btn {
  position: relative;
  background: none;
  border: none;
  color: var(--ss-text-secondary);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.4rem;
  border-radius: var(--ss-radius-sm);
  transition: all var(--ss-transition-fast);
}

.topbar-icon-btn:hover {
  background: var(--ss-bg-elevated);
  color: var(--ss-text-primary);
}

.topbar-badge {
  position: absolute;
  top: 0;
  right: 0;
  background: var(--ss-danger);
  color: white;
  font-size: 0.6rem;
  font-weight: 700;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* User dropdown */
.user-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.5rem;
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  box-shadow: var(--ss-shadow-lg);
  min-width: 200px;
  z-index: 200;
  padding: 0.5rem 0;
}

.dropdown-header {
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.85rem;
}

.dropdown-divider {
  height: 1px;
  background: var(--ss-border-light);
  margin: 0.25rem 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.6rem 1rem;
  background: none;
  border: none;
  color: var(--ss-text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.dropdown-item:hover {
  background: var(--ss-accent-dim);
  color: var(--ss-text-primary);
}

.dropdown-item--danger:hover {
  background: rgba(239, 68, 68, 0.1);
  color: var(--ss-danger);
}

/* ── Page content ── */
.page-content {
  flex: 1;
  overflow-y: auto;
}

/* ── Overlay ── */
.sidebar-overlay {
  display: none;
}

/* ── Text transition ── */
.fade-text-enter-active,
.fade-text-leave-active {
  transition: opacity var(--ss-transition-fast);
}
.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform var(--ss-transition);
    width: var(--ss-sidebar-width) !important;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 90;
  }

  .main-area {
    margin-left: 0 !important;
  }

  .mobile-menu-btn {
    display: flex;
  }

  .collapse-btn {
    display: none;
  }

  .topbar-search {
    display: none;
  }
}
</style>
