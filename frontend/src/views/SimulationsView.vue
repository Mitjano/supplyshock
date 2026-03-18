<template>
  <div class="simulations-view fade-in">
    <!-- Header -->
    <header class="sim-header">
      <div class="header-left">
        <h1>{{ t('simulations.title') }}</h1>
      </div>
    </header>

    <!-- Upgrade Banner (free plan) -->
    <div v-if="auth.plan === 'free'" class="upgrade-banner">
      <div class="upgrade-content">
        <i class="pi pi-lock" />
        <div>
          <strong>{{ t('simulations.upgradeBannerTitle') }}</strong>
          <p>{{ t('simulations.upgradeBannerDesc') }}</p>
        </div>
      </div>
      <button class="upgrade-btn" @click="auth.signIn()">
        {{ t('simulations.upgradePlan') }}
      </button>
    </div>

    <!-- New Simulation Form -->
    <section class="form-section ss-card">
      <div class="form-header" @click="formExpanded = !formExpanded">
        <div class="form-header-left">
          <i class="pi pi-play-circle" />
          <h2>{{ t('simulations.newSimulation') }}</h2>
        </div>
        <button class="toggle-btn">
          <i :class="['pi', formExpanded ? 'pi-chevron-up' : 'pi-chevron-down']" />
        </button>
      </div>

      <Transition name="slide">
        <div v-show="formExpanded" class="form-body">
          <!-- Row 1: Title + Node -->
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">{{ t('simulations.titleLabel') }} <span class="required">*</span></label>
              <input
                v-model="form.title"
                type="text"
                class="form-input"
                :class="{ 'input-error': submitted && !form.title.trim() }"
                :placeholder="t('simulations.titlePlaceholder')"
              />
              <span v-if="submitted && !form.title.trim()" class="error-text">{{ t('simulations.titleRequired') }}</span>
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('simulations.nodeLabel') }} <span class="required">*</span></label>
              <select
                v-model="form.node"
                class="form-input form-select"
                :class="{ 'input-error': submitted && !form.node }"
              >
                <option value="" disabled>{{ t('simulations.selectNode') }}</option>
                <option v-for="node in bottleneckNodes" :key="node.slug" :value="node.slug">
                  {{ node.name }} ({{ node.type }})
                </option>
              </select>
              <span v-if="submitted && !form.node" class="error-text">{{ t('simulations.nodeRequired') }}</span>
            </div>
          </div>

          <!-- Row 2: Event + Description -->
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">{{ t('simulations.eventTypeLabel') }}</label>
              <select v-model="form.eventType" class="form-input form-select">
                <option v-for="evt in eventTypes" :key="evt.value" :value="evt.value">
                  {{ evt.label }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('simulations.descriptionLabel') }}</label>
              <textarea
                v-model="form.description"
                class="form-input form-textarea"
                rows="3"
                :placeholder="t('simulations.descriptionPlaceholder')"
              />
            </div>
          </div>

          <!-- Parameters -->
          <div class="form-params-header" @click="advancedOpen = !advancedOpen">
            <span class="params-toggle-label">
              <i :class="['pi', advancedOpen ? 'pi-chevron-down' : 'pi-chevron-right']" />
              {{ t('simulations.advancedParams') }}
            </span>
          </div>

          <Transition name="slide">
            <div v-show="advancedOpen" class="params-grid">
              <div class="form-group">
                <label class="form-label">{{ t('simulations.durationWeeks') }}</label>
                <input
                  v-model.number="form.durationWeeks"
                  type="number"
                  class="form-input"
                  min="1"
                  max="52"
                />
              </div>

              <div class="form-group">
                <label class="form-label">
                  {{ t('simulations.intensity') }}
                  <span class="intensity-value">{{ form.intensity }}</span>
                </label>
                <div class="slider-wrapper">
                  <input
                    v-model.number="form.intensity"
                    type="range"
                    min="1"
                    max="10"
                    class="form-slider"
                  />
                  <div class="slider-labels">
                    <span>1</span>
                    <span>10</span>
                  </div>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">{{ t('simulations.agentsCount') }}</label>
                <input
                  v-model.number="form.agentsCount"
                  type="number"
                  class="form-input"
                  min="10"
                  max="1000"
                  step="10"
                />
              </div>

              <div class="form-group">
                <label class="form-label">{{ t('simulations.horizonDays') }}</label>
                <input
                  v-model.number="form.horizonDays"
                  type="number"
                  class="form-input"
                  min="7"
                  max="365"
                />
              </div>
            </div>
          </Transition>

          <!-- Submit -->
          <div class="form-actions">
            <button
              class="run-btn"
              :disabled="submitting"
              @click="handleSubmit"
            >
              <i :class="['pi', submitting ? 'pi-spin pi-spinner' : 'pi-play']" />
              {{ t('simulations.runSimulation') }}
            </button>
          </div>
        </div>
      </Transition>
    </section>

    <!-- Live Progress Log -->
    <section v-if="liveLog.length" class="live-log-section ss-card">
      <div class="live-log-header">
        <div class="live-dot" />
        <h3>{{ t('simulations.liveProgress') }}</h3>
      </div>
      <div class="live-log-scroll" ref="logScrollRef">
        <div v-for="(line, idx) in liveLog" :key="idx" class="log-line">
          <span class="log-time">{{ String(idx + 1).padStart(2, '0') }}</span>
          <span class="log-text">{{ line }}</span>
        </div>
      </div>
    </section>

    <!-- Past Simulations -->
    <section class="history-section">
      <div class="section-header">
        <h2>{{ t('simulations.pastSimulations') }}</h2>
        <button class="refresh-btn" @click="fetchSimulations" :disabled="loading">
          <i class="pi pi-refresh" :class="{ spin: loading }" />
        </button>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading && !simulations.length" class="skeleton-list">
        <div v-for="i in 4" :key="i" class="skeleton-card">
          <div class="skeleton-bar skeleton-title" />
          <div class="skeleton-bar skeleton-body" />
          <div class="skeleton-bar skeleton-meta" />
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!simulations.length" class="empty-state">
        <div class="empty-illustration">
          <i class="pi pi-chart-scatter" />
        </div>
        <h3>{{ t('simulations.emptyTitle') }}</h3>
        <p>{{ t('simulations.emptyDesc') }}</p>
      </div>

      <!-- Desktop Table -->
      <div v-else class="sim-table-wrapper desktop-only">
        <table class="sim-table">
          <thead>
            <tr>
              <th>{{ t('simulations.colTitle') }}</th>
              <th>{{ t('simulations.colNode') }}</th>
              <th>{{ t('simulations.colEvent') }}</th>
              <th>{{ t('simulations.colStatus') }}</th>
              <th>{{ t('simulations.colProgress') }}</th>
              <th>{{ t('simulations.colCreated') }}</th>
              <th>{{ t('simulations.colActions') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="sim in simulations" :key="sim.id">
              <tr
                :class="{ 'row-expanded': expandedId === sim.id }"
                @click="toggleExpand(sim)"
              >
                <td class="col-title">{{ sim.title }}</td>
                <td class="col-node">{{ formatNodeName(sim.node) }}</td>
                <td class="col-event">
                  <span class="event-chip">{{ formatEventType(sim.event_type) }}</span>
                </td>
                <td>
                  <span :class="['status-badge', `status-${sim.status}`]">
                    {{ t(`simulations.status.${sim.status}`) }}
                  </span>
                </td>
                <td class="col-progress">
                  <div class="progress-bar-track">
                    <div
                      :class="['progress-bar-fill', `progress-${sim.status}`]"
                      :style="{ width: `${sim.progress}%` }"
                    />
                  </div>
                  <span class="progress-text">{{ sim.progress }}%</span>
                </td>
                <td class="col-date">{{ formatDate(sim.created_at) }}</td>
                <td class="col-actions">
                  <button
                    v-if="sim.status === 'completed'"
                    class="action-btn"
                    :title="t('simulations.viewResults')"
                    @click.stop="toggleExpand(sim)"
                  >
                    <i :class="['pi', expandedId === sim.id ? 'pi-chevron-up' : 'pi-chevron-down']" />
                  </button>
                  <button
                    class="action-btn action-delete"
                    :title="t('common.delete')"
                    @click.stop="deleteSimulation(sim.id)"
                  >
                    <i class="pi pi-trash" />
                  </button>
                </td>
              </tr>
              <!-- Expanded result row -->
              <tr v-if="expandedId === sim.id && sim.status === 'completed' && sim.result" class="expanded-row">
                <td colspan="7">
                  <div class="result-panel fade-in">
                    <h4>{{ t('simulations.resultsSummary') }}</h4>
                    <div class="result-grid">
                      <div v-if="sim.result.risk_score != null" class="result-item">
                        <span class="result-label">{{ t('simulations.riskScore') }}</span>
                        <span class="result-value">{{ sim.result.risk_score }}/10</span>
                      </div>
                      <div v-if="sim.result.global_share_pct != null" class="result-item">
                        <span class="result-label">{{ t('simulations.globalShare') }}</span>
                        <span class="result-value">{{ sim.result.global_share_pct }}%</span>
                      </div>
                      <div v-for="(pred, commodity) in (sim.result.predictions || {})" :key="commodity" class="result-item">
                        <span class="result-label">{{ formatCommodity(commodity as string) }}</span>
                        <span :class="['result-value', pred.peak_change_pct > 0 ? 'text-danger' : 'text-success']">
                          {{ pred.peak_change_pct > 0 ? '+' : '' }}{{ pred.peak_change_pct }}%
                        </span>
                      </div>
                    </div>
                    <p v-if="sim.result.summary" class="result-summary">{{ sim.result.summary }}</p>

                    <!-- OASIS multi-agent details -->
                    <div v-if="sim.result.simulation_type === 'multi_agent'" class="oasis-details">
                      <span class="oasis-badge">Multi-Agent OASIS</span>
                      <span class="oasis-meta">{{ sim.result.agent_count }} agents · {{ sim.result.steps }} rounds · {{ sim.result.elapsed_seconds }}s</span>
                      <div v-if="sim.result.agent_summary" class="oasis-summary">
                        <div v-if="sim.result.agent_summary.trade_distribution?.length" class="oasis-trades">
                          <span class="result-label">{{ t('simulations.tradeActions') }}</span>
                          <span v-for="t in sim.result.agent_summary.trade_distribution" :key="t.action" class="trade-chip">
                            {{ t.action }}: {{ t.count }}
                          </span>
                        </div>
                        <div v-if="sim.result.agent_summary.reroute_patterns?.length" class="oasis-reroutes">
                          <span class="result-label">{{ t('simulations.vesselReroutes') }}</span>
                          <span v-for="r in sim.result.agent_summary.reroute_patterns" :key="r.port" class="trade-chip">
                            → {{ r.port }}: {{ r.count }}
                          </span>
                        </div>
                      </div>
                    </div>
                    <span v-else-if="sim.result.simulation_type === 'deterministic'" class="deterministic-badge">Deterministic Model</span>
                  </div>
                </td>
              </tr>
              <!-- Error row -->
              <tr v-if="expandedId === sim.id && sim.status === 'failed'" class="expanded-row">
                <td colspan="7">
                  <div class="result-panel error-panel fade-in">
                    <i class="pi pi-exclamation-triangle" />
                    <span>{{ sim.error_message || t('simulations.unknownError') }}</span>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Mobile Card List -->
      <div v-if="simulations.length" class="sim-cards mobile-only">
        <div
          v-for="sim in simulations"
          :key="sim.id"
          class="sim-card"
          @click="toggleExpand(sim)"
        >
          <div class="sim-card-top">
            <span class="sim-card-title">{{ sim.title }}</span>
            <span :class="['status-badge', `status-${sim.status}`]">
              {{ t(`simulations.status.${sim.status}`) }}
            </span>
          </div>
          <div class="sim-card-meta">
            <span class="event-chip">{{ formatEventType(sim.event_type) }}</span>
            <span class="text-muted">{{ formatNodeName(sim.node) }}</span>
          </div>
          <div class="sim-card-progress">
            <div class="progress-bar-track">
              <div
                :class="['progress-bar-fill', `progress-${sim.status}`]"
                :style="{ width: `${sim.progress}%` }"
              />
            </div>
            <span class="progress-text">{{ sim.progress }}%</span>
          </div>
          <div class="sim-card-footer">
            <span class="text-muted">{{ formatDate(sim.created_at) }}</span>
            <button class="action-btn action-delete" @click.stop="deleteSimulation(sim.id)">
              <i class="pi pi-trash" />
            </button>
          </div>

          <!-- Expanded results (mobile) -->
          <div v-if="expandedId === sim.id && sim.status === 'completed' && sim.result" class="result-panel fade-in">
            <h4>{{ t('simulations.resultsSummary') }}</h4>
            <div class="result-grid">
              <div v-if="sim.result.risk_score != null" class="result-item">
                <span class="result-label">{{ t('simulations.riskScore') }}</span>
                <span class="result-value">{{ sim.result.risk_score }}/10</span>
              </div>
              <div v-for="(pred, commodity) in (sim.result.predictions || {})" :key="commodity" class="result-item">
                <span class="result-label">{{ formatCommodity(commodity as string) }}</span>
                <span :class="['result-value', pred.peak_change_pct > 0 ? 'text-danger' : 'text-success']">
                  {{ pred.peak_change_pct > 0 ? '+' : '' }}{{ pred.peak_change_pct }}%
                </span>
              </div>
            </div>
            <p v-if="sim.result.summary" class="result-summary">{{ sim.result.summary }}</p>

            <!-- OASIS multi-agent details (mobile) -->
            <div v-if="sim.result.simulation_type === 'multi_agent'" class="oasis-details">
              <span class="oasis-badge">Multi-Agent OASIS</span>
              <span class="oasis-meta">{{ sim.result.agent_count }} agents · {{ sim.result.steps }} rounds</span>
            </div>
            <span v-else-if="sim.result.simulation_type === 'deterministic'" class="deterministic-badge">Deterministic</span>
          </div>
          <div v-if="expandedId === sim.id && sim.status === 'failed'" class="result-panel error-panel fade-in">
            <i class="pi pi-exclamation-triangle" />
            <span>{{ sim.error_message || t('simulations.unknownError') }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toast.visible" :class="['toast', `toast-${toast.type}`]">
        <i :class="['pi', toast.type === 'success' ? 'pi-check-circle' : 'pi-exclamation-circle']" />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useApi } from '@/composables/useApi'
import { useAuthStore } from '@/stores/useAuthStore'

const { t } = useI18n()
const api = useApi()
const auth = useAuthStore()
const route = useRoute()

// ---------- Types ----------
interface BottleneckNode {
  slug: string
  name: string
  type: string
}

interface PredictionEntry {
  benchmark: string
  baseline_price: number
  weekly_prices: number[]
  peak_price: number
  peak_change_pct: number
  recovery_week: number
}

interface SimulationResult {
  risk_score?: number
  global_share_pct?: number
  predictions?: Record<string, PredictionEntry>
  summary?: string
  node_name?: string
  event_type?: string
  [key: string]: unknown
}

interface Simulation {
  id: string
  title: string
  node: string
  event_type: string
  description: string | null
  parameters: Record<string, unknown>
  status: 'queued' | 'running' | 'completed' | 'failed' | 'timeout'
  progress: number
  result: SimulationResult | null
  error_message: string | null
  agents_count: number | null
  created_at: string
}

// ---------- State ----------
const formExpanded = ref(true)
const advancedOpen = ref(false)
const submitted = ref(false)
const submitting = ref(false)
const loading = ref(false)
const bottleneckNodes = ref<BottleneckNode[]>([])
const simulations = ref<Simulation[]>([])
const expandedId = ref<string | null>(null)

const form = reactive({
  title: '',
  node: '',
  eventType: 'flood',
  description: '',
  durationWeeks: 4,
  intensity: 5,
  agentsCount: 100,
  horizonDays: 90,
})

const toast = reactive({
  visible: false,
  type: 'success' as 'success' | 'error',
  message: '',
})

const liveLog = ref<string[]>([])
const activeSSE = ref<EventSource | null>(null)

let toastTimer: ReturnType<typeof setTimeout> | null = null
let pollInterval: ReturnType<typeof setInterval> | null = null

// ---------- Event Types ----------
const eventTypes = [
  { value: 'flood', label: 'Flood' },
  { value: 'strike', label: 'Strike' },
  { value: 'blockade', label: 'Blockade' },
  { value: 'earthquake', label: 'Earthquake' },
  { value: 'storm', label: 'Storm' },
  { value: 'sanctions', label: 'Sanctions' },
  { value: 'piracy', label: 'Piracy' },
  { value: 'infrastructure_failure', label: 'Infrastructure Failure' },
]

// ---------- Functions ----------
function showToast(type: 'success' | 'error', message: string) {
  toast.visible = true
  toast.type = type
  toast.message = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.visible = false }, 4000)
}

function formatNodeName(slug: string): string {
  const node = bottleneckNodes.value.find(n => n.slug === slug)
  if (node) return node.name
  return slug.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatEventType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatCommodity(commodity: string): string {
  return commodity.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function connectSSE(simulationId: string) {
  if (activeSSE.value) {
    activeSSE.value.close()
  }
  liveLog.value = []

  const baseUrl = import.meta.env.VITE_API_URL || ''
  const token = auth.token
  const url = `${baseUrl}/api/v1/simulations/${simulationId}/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`

  const eventSource = new EventSource(url)
  activeSSE.value = eventSource

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      // Update simulation in list
      const sim = simulations.value.find(s => s.id === simulationId)
      if (sim) {
        if (data.progress != null) sim.progress = data.progress
        if (data.log) liveLog.value.push(data.log)
        if (data.status === 'completed') {
          sim.status = 'completed'
          eventSource.close()
          activeSSE.value = null
          fetchSimulations() // reload to get full result
        }
        if (data.status === 'failed') {
          sim.status = 'failed'
          sim.error_message = data.error || 'Unknown error'
          eventSource.close()
          activeSSE.value = null
        }
      }
    } catch {
      // Ignore parse errors (keepalive comments)
    }
  }

  eventSource.onerror = () => {
    eventSource.close()
    activeSSE.value = null
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function toggleExpand(sim: Simulation) {
  if (sim.status !== 'completed' && sim.status !== 'failed') return
  expandedId.value = expandedId.value === sim.id ? null : sim.id
}

async function fetchBottlenecks() {
  try {
    const res = await api.get<{ data: BottleneckNode[] }>('/bottlenecks')
    bottleneckNodes.value = res.data
  } catch (e) {
    console.error('Failed to fetch bottlenecks:', e)
  }
}

async function fetchSimulations() {
  loading.value = true
  try {
    const res = await api.get<{ data: Simulation[] }>('/simulations')
    simulations.value = res.data
  } catch (e) {
    // API might not exist yet — silently fail
    console.error('Failed to fetch simulations:', e)
    simulations.value = []
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  submitted.value = true

  if (!form.title.trim() || !form.node) return

  submitting.value = true
  try {
    const payload = {
      title: form.title.trim(),
      node: form.node,
      event_type: form.eventType,
      description: form.description.trim() || null,
      parameters: {
        duration_weeks: form.durationWeeks,
        intensity: form.intensity,
        horizon_days: form.horizonDays,
      },
      agents_count: form.agentsCount,
    }

    const res = await api.post<{ id: string }>('/simulations', payload)
    showToast('success', t('simulations.submitted'))

    // Reset form
    form.title = ''
    form.description = ''
    form.eventType = 'flood'
    form.durationWeeks = 4
    form.intensity = 5
    form.agentsCount = 100
    form.horizonDays = 90
    submitted.value = false

    // Refresh list and connect SSE for live progress
    await fetchSimulations()
    if (res.id) {
      connectSSE(res.id)
    }
  } catch {
    showToast('error', t('simulations.submitFailed'))
  } finally {
    submitting.value = false
  }
}

async function deleteSimulation(id: string) {
  try {
    await api.del(`/simulations/${id}`)
    simulations.value = simulations.value.filter(s => s.id !== id)
    if (expandedId.value === id) expandedId.value = null
    showToast('success', t('simulations.deleted'))
  } catch {
    showToast('error', t('simulations.deleteFailed'))
  }
}

// ---------- Lifecycle ----------
onMounted(async () => {
  await fetchBottlenecks()

  // Pre-select node from query param (from BottleneckMonitor)
  const nodeQuery = route.query.node as string | undefined
  if (nodeQuery) {
    form.node = nodeQuery
  }

  await fetchSimulations()

  // Poll running simulations every 10s
  pollInterval = setInterval(async () => {
    const hasRunning = simulations.value.some(s => s.status === 'queued' || s.status === 'running')
    if (hasRunning) {
      await fetchSimulations()
    }
  }, 10_000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (toastTimer) clearTimeout(toastTimer)
  if (activeSSE.value) activeSSE.value.close()
})
</script>

<style scoped>
/* ========== Layout ========== */
.simulations-view {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
  color: var(--ss-text-primary);
  min-height: 100vh;
}

/* ========== Header ========== */
.sim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.sim-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0;
}

/* ========== Upgrade Banner ========== */
.upgrade-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(245, 158, 11, 0.05));
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: var(--ss-radius-lg);
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
}

.upgrade-content {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.upgrade-content i {
  font-size: 1.5rem;
  color: var(--ss-warning);
}

.upgrade-content strong {
  display: block;
  font-size: 0.9rem;
  margin-bottom: 0.15rem;
}

.upgrade-content p {
  margin: 0;
  font-size: 0.8rem;
  color: var(--ss-text-secondary);
}

.upgrade-btn {
  background: var(--ss-warning);
  color: #0f172a;
  border: none;
  padding: 0.5rem 1.25rem;
  border-radius: var(--ss-radius);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--ss-transition-fast);
}

.upgrade-btn:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

/* ========== Form Section ========== */
.form-section {
  margin-bottom: 2rem;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.form-header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.form-header-left i {
  font-size: 1.2rem;
  color: var(--ss-accent);
}

.form-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--ss-text-muted);
  cursor: pointer;
  padding: 0.25rem;
  font-size: 0.9rem;
}

.form-body {
  padding-top: 1.25rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ss-text-muted);
  font-weight: 600;
}

.required {
  color: var(--ss-danger);
}

.form-input {
  background: var(--ss-bg-base);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  padding: 0.6rem 0.85rem;
  color: var(--ss-text-primary);
  font-size: 0.875rem;
  outline: none;
  transition: border-color var(--ss-transition-fast);
  font-family: inherit;
}

.form-input:focus {
  border-color: var(--ss-accent);
}

.form-input::placeholder {
  color: var(--ss-text-muted);
}

.form-input.input-error {
  border-color: var(--ss-danger);
}

.error-text {
  font-size: 0.7rem;
  color: var(--ss-danger);
}

.form-select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2394a3b8' d='M2 4l4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.75rem center;
  padding-right: 2rem;
}

.form-select option {
  background: var(--ss-bg-surface);
  color: var(--ss-text-primary);
}

.form-textarea {
  resize: vertical;
  min-height: 70px;
}

/* ---- Advanced Params ---- */
.form-params-header {
  cursor: pointer;
  padding: 0.5rem 0;
  margin-bottom: 0.5rem;
  user-select: none;
}

.params-toggle-label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: var(--ss-text-secondary);
  font-weight: 500;
}

.params-toggle-label i {
  font-size: 0.65rem;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}

/* Slider */
.slider-wrapper {
  display: flex;
  flex-direction: column;
}

.intensity-value {
  font-weight: 700;
  color: var(--ss-accent);
  margin-left: 0.3rem;
}

.form-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  background: var(--ss-bg-elevated);
  border-radius: 3px;
  outline: none;
  margin-top: 0.5rem;
}

.form-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--ss-accent);
  cursor: pointer;
  border: 2px solid var(--ss-bg-surface);
  box-shadow: 0 0 4px rgba(20, 184, 166, 0.4);
}

.form-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--ss-accent);
  cursor: pointer;
  border: 2px solid var(--ss-bg-surface);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.65rem;
  color: var(--ss-text-muted);
  margin-top: 0.2rem;
}

/* Submit */
.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 0.5rem;
  border-top: 1px solid var(--ss-border);
}

.run-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--ss-accent);
  color: #fff;
  border: none;
  padding: 0.7rem 2rem;
  border-radius: var(--ss-radius);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.run-btn:hover:not(:disabled) {
  background: var(--ss-accent-light);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3);
}

.run-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ========== Live Log ========== */
.live-log-section {
  margin-bottom: 1.5rem;
  border-color: rgba(59, 130, 246, 0.3);
}

.live-log-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.live-log-header h3 {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.live-log-scroll {
  max-height: 200px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.78rem;
  line-height: 1.7;
  background: var(--ss-bg-base);
  border-radius: var(--ss-radius);
  padding: 0.75rem 1rem;
}

.log-line {
  display: flex;
  gap: 0.75rem;
}

.log-time {
  color: var(--ss-text-muted);
  flex-shrink: 0;
  opacity: 0.5;
}

.log-text {
  color: var(--ss-accent-light, #5eead4);
}

/* ========== History Section ========== */
.history-section {
  margin-top: 0.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
}

.refresh-btn {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  color: var(--ss-text-secondary);
  width: 36px;
  height: 36px;
  border-radius: var(--ss-radius);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--ss-transition-fast);
}

.refresh-btn:hover {
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ========== Table ========== */
.sim-table-wrapper {
  overflow-x: auto;
}

.sim-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.sim-table thead th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ss-text-muted);
  font-weight: 600;
  border-bottom: 1px solid var(--ss-border-light);
  white-space: nowrap;
}

.sim-table tbody tr {
  border-bottom: 1px solid var(--ss-border);
  transition: background var(--ss-transition-fast);
  cursor: default;
}

.sim-table tbody tr:hover {
  background: rgba(30, 41, 59, 0.5);
}

.sim-table tbody tr.row-expanded {
  background: rgba(20, 184, 166, 0.05);
}

.sim-table td {
  padding: 0.75rem 1rem;
  vertical-align: middle;
}

.col-title {
  font-weight: 600;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-node {
  color: var(--ss-text-secondary);
  white-space: nowrap;
}

.col-date {
  color: var(--ss-text-muted);
  font-size: 0.8rem;
  white-space: nowrap;
}

.event-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  background: var(--ss-bg-elevated);
  color: var(--ss-text-secondary);
  text-transform: capitalize;
  white-space: nowrap;
}

/* Status badges */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.status-queued {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
}

.status-running {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  animation: pulse-status 2s ease-in-out infinite;
}

.status-completed {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.status-timeout {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

@keyframes pulse-status {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* Progress bar */
.col-progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 120px;
}

.progress-bar-track {
  flex: 1;
  height: 6px;
  background: var(--ss-bg-base);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress-queued { background: #64748b; }
.progress-running {
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  animation: progress-shimmer 1.5s ease-in-out infinite;
}
.progress-completed { background: #22c55e; }
.progress-failed { background: #ef4444; }
.progress-timeout { background: #f59e0b; }

@keyframes progress-shimmer {
  0% { opacity: 0.7; }
  50% { opacity: 1; }
  100% { opacity: 0.7; }
}

.progress-text {
  font-size: 0.75rem;
  color: var(--ss-text-muted);
  min-width: 32px;
  text-align: right;
}

/* Actions */
.col-actions {
  display: flex;
  gap: 0.3rem;
}

.action-btn {
  background: none;
  border: 1px solid transparent;
  color: var(--ss-text-muted);
  width: 30px;
  height: 30px;
  border-radius: var(--ss-radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--ss-transition-fast);
  font-size: 0.8rem;
}

.action-btn:hover {
  background: var(--ss-bg-elevated);
  color: var(--ss-text-primary);
  border-color: var(--ss-border-light);
}

.action-delete:hover {
  color: var(--ss-danger);
  border-color: rgba(239, 68, 68, 0.3);
}

/* Expanded row */
.expanded-row td {
  padding: 0;
  border-bottom: 1px solid var(--ss-border);
}

.result-panel {
  padding: 1.25rem 1.5rem;
  background: rgba(20, 184, 166, 0.03);
}

.result-panel h4 {
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  color: var(--ss-text-primary);
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.result-item {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  padding: 0.75rem;
  text-align: center;
}

.result-label {
  display: block;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ss-text-muted);
  margin-bottom: 0.25rem;
}

.result-value {
  font-size: 1.1rem;
  font-weight: 700;
}

.result-summary {
  color: var(--ss-text-secondary);
  font-size: 0.85rem;
  line-height: 1.6;
  margin: 0;
}

/* OASIS multi-agent result details */
.oasis-details {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--ss-border, rgba(255,255,255,0.06));
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.oasis-badge {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.deterministic-badge {
  background: rgba(100, 116, 139, 0.15);
  color: var(--ss-text-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 500;
}

.oasis-meta {
  color: var(--ss-text-secondary);
  font-size: 0.78rem;
}

.oasis-summary {
  width: 100%;
  margin-top: 0.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.oasis-trades, .oasis-reroutes {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.trade-chip {
  background: rgba(139, 92, 246, 0.1);
  color: var(--ss-text-primary);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
}

.error-panel {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: rgba(239, 68, 68, 0.05);
  color: #f87171;
  font-size: 0.85rem;
}

.error-panel i {
  font-size: 1.1rem;
}

/* ========== Mobile Card List ========== */
.sim-cards {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.sim-card {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: border-color var(--ss-transition-fast);
}

.sim-card:hover {
  border-color: var(--ss-text-muted);
}

.sim-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.sim-card-title {
  font-weight: 600;
  font-size: 0.9rem;
}

.sim-card-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.8rem;
}

.sim-card-progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.sim-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
}

/* ========== Empty State ========== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-illustration {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--ss-bg-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.empty-illustration i {
  font-size: 2rem;
  color: var(--ss-text-muted);
  opacity: 0.5;
}

.empty-state h3 {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
  color: var(--ss-text-secondary);
}

.empty-state p {
  margin: 0;
  color: var(--ss-text-muted);
  font-size: 0.85rem;
  max-width: 360px;
}

/* ========== Skeleton ========== */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.skeleton-card {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1.25rem;
}

.skeleton-bar {
  background: linear-gradient(90deg, var(--ss-bg-elevated) 25%, rgba(100, 116, 139, 0.15) 50%, var(--ss-bg-elevated) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.skeleton-title { width: 65%; height: 16px; margin-bottom: 0.75rem; }
.skeleton-body { width: 90%; height: 12px; margin-bottom: 0.5rem; }
.skeleton-meta { width: 40%; height: 10px; }

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

/* ========== Toast ========== */
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 1.25rem;
  border-radius: var(--ss-radius);
  font-size: 0.85rem;
  font-weight: 500;
  box-shadow: var(--ss-shadow-lg);
  z-index: 1000;
}

.toast-success {
  background: #065f46;
  color: #6ee7b7;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.toast-error {
  background: #7f1d1d;
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

/* ========== Transitions ========== */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 800px;
}

/* ========== Responsive helpers ========== */
.mobile-only {
  display: none;
}

/* ========== Responsive: Tablet ========== */
@media (max-width: 1024px) {
  .params-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* ========== Responsive: Mobile ========== */
@media (max-width: 768px) {
  .simulations-view {
    padding: 1rem;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .params-grid {
    grid-template-columns: 1fr 1fr;
  }

  .upgrade-banner {
    flex-direction: column;
    gap: 0.75rem;
    text-align: center;
  }

  .upgrade-content {
    flex-direction: column;
    text-align: center;
  }

  .desktop-only {
    display: none !important;
  }

  .mobile-only {
    display: flex !important;
  }

  .run-btn {
    width: 100%;
    justify-content: center;
  }

  .form-actions {
    justify-content: stretch;
  }
}

@media (max-width: 480px) {
  .params-grid {
    grid-template-columns: 1fr;
  }
}
</style>
