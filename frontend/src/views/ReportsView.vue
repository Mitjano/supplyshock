<template>
  <div class="reports-view fade-in">
    <!-- Header -->
    <header class="reports-header">
      <div class="header-left">
        <h1>{{ t('reports.title') }}</h1>
        <span class="report-count-badge" v-if="reports.length">{{ reports.length }}</span>
      </div>
      <button class="btn-primary" @click="showGenerateDialog = true">
        <i class="pi pi-plus" />
        {{ t('reports.generate') }}
      </button>
    </header>

    <!-- Plan Limit Banner (free users) -->
    <div v-if="!isPro && reports.length >= 3" class="plan-banner">
      <i class="pi pi-lock" />
      <span>{{ t('reports.planLimit') }}</span>
      <router-link to="/settings" class="plan-upgrade-link">{{ t('reports.upgradePlan') }}</router-link>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="loading && !reports.length" class="reports-grid">
      <div v-for="i in 4" :key="i" class="skeleton-card">
        <div class="skeleton-bar skeleton-title" />
        <div class="skeleton-bar skeleton-body" />
        <div class="skeleton-bar skeleton-meta" />
        <div class="skeleton-bar skeleton-actions" />
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!reports.length" class="empty-state">
      <div class="empty-icon-wrap">
        <i class="pi pi-file-pdf empty-icon" />
      </div>
      <h3>{{ t('reports.emptyTitle') }}</h3>
      <p>{{ t('reports.emptyDesc') }}</p>
      <button class="btn-primary btn-lg" @click="showGenerateDialog = true">
        <i class="pi pi-plus" />
        {{ t('reports.generateFirst') }}
      </button>
    </div>

    <!-- Reports Grid -->
    <TransitionGroup v-else name="report-list" tag="div" class="reports-grid">
      <div v-for="report in reports" :key="report.id" class="report-card">
        <div class="report-card-top">
          <div class="report-title-row">
            <h3 class="report-title">{{ report.title }}</h3>
            <span :class="['status-badge', `status-${report.status}`]">
              <i v-if="report.status === 'generating'" class="pi pi-spinner spin" />
              <i v-else-if="report.status === 'ready'" class="pi pi-check-circle" />
              <i v-else class="pi pi-times-circle" />
              {{ t(`reports.status.${report.status}`) }}
            </span>
          </div>

          <div class="report-meta">
            <span v-if="report.page_count" class="meta-item">
              <i class="pi pi-file" />
              {{ t('reports.pages', { n: report.page_count }) }}
            </span>
            <span v-if="report.file_size_bytes" class="meta-item">
              <i class="pi pi-database" />
              {{ formatFileSize(report.file_size_bytes) }}
            </span>
            <span class="meta-item">
              <i class="pi pi-calendar" />
              {{ formatDate(report.created_at) }}
            </span>
          </div>

          <router-link
            v-if="report.simulation_id"
            :to="`/simulations/${report.simulation_id}`"
            class="simulation-link"
          >
            <i class="pi pi-play-circle" />
            {{ t('reports.linkedSimulation') }}
          </router-link>
        </div>

        <div class="report-actions">
          <button
            class="action-btn action-download"
            :disabled="report.status !== 'ready'"
            @click="downloadReport(report)"
            :title="t('reports.download')"
          >
            <i class="pi pi-download" />
            {{ t('reports.download') }}
          </button>
          <button
            class="action-btn action-share"
            :disabled="report.status !== 'ready'"
            @click="shareReport(report)"
            :title="t('reports.share')"
          >
            <i class="pi pi-share-alt" />
            {{ t('reports.share') }}
          </button>
          <button
            class="action-btn action-delete"
            @click="confirmDelete(report)"
            :title="t('common.delete')"
          >
            <i class="pi pi-trash" />
          </button>
        </div>
      </div>
    </TransitionGroup>

    <!-- Toast Notification -->
    <Transition name="toast-slide">
      <div v-if="toast.visible" :class="['toast', `toast-${toast.type}`]">
        <i :class="['pi', toast.type === 'success' ? 'pi-check-circle' : 'pi-exclamation-circle']" />
        {{ toast.message }}
      </div>
    </Transition>

    <!-- Generate Report Dialog -->
    <Transition name="dialog-fade">
      <div v-if="showGenerateDialog" class="dialog-overlay" @click.self="showGenerateDialog = false">
        <div class="dialog-panel">
          <div class="dialog-header">
            <h2>{{ t('reports.generateTitle') }}</h2>
            <button class="dialog-close" @click="showGenerateDialog = false">
              <i class="pi pi-times" />
            </button>
          </div>

          <div class="dialog-body">
            <div class="form-group">
              <label class="form-label">{{ t('reports.form.title') }}</label>
              <input
                v-model="form.title"
                type="text"
                class="form-input"
                :placeholder="t('reports.form.titlePlaceholder')"
              />
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('reports.form.simulation') }}</label>
              <select v-model="form.simulation_id" class="form-input">
                <option value="">{{ t('reports.form.noSimulation') }}</option>
                <option v-for="sim in simulations" :key="sim.id" :value="sim.id">
                  {{ sim.title }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('reports.form.type') }}</label>
              <select v-model="form.report_type" class="form-input">
                <option v-for="rt in reportTypes" :key="rt.value" :value="rt.value">
                  {{ rt.label }}
                </option>
              </select>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">{{ t('reports.form.dateFrom') }}</label>
                <input v-model="form.date_from" type="date" class="form-input" />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('reports.form.dateTo') }}</label>
                <input v-model="form.date_to" type="date" class="form-input" />
              </div>
            </div>
          </div>

          <div class="dialog-footer">
            <button class="btn-secondary" @click="showGenerateDialog = false">
              {{ t('common.cancel') }}
            </button>
            <button
              class="btn-primary"
              :disabled="!form.title.trim() || generating"
              @click="generateReport"
            >
              <i v-if="generating" class="pi pi-spinner spin" />
              <i v-else class="pi pi-file-pdf" />
              {{ t('reports.generate') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Delete Confirmation Dialog -->
    <Transition name="dialog-fade">
      <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
        <div class="dialog-panel dialog-sm">
          <div class="dialog-header">
            <h2>{{ t('reports.deleteTitle') }}</h2>
            <button class="dialog-close" @click="deleteTarget = null">
              <i class="pi pi-times" />
            </button>
          </div>
          <div class="dialog-body">
            <p class="delete-message">
              {{ t('reports.deleteConfirm', { title: deleteTarget.title }) }}
            </p>
          </div>
          <div class="dialog-footer">
            <button class="btn-secondary" @click="deleteTarget = null">
              {{ t('common.cancel') }}
            </button>
            <button class="btn-danger" :disabled="deleting" @click="executeDelete">
              <i v-if="deleting" class="pi pi-spinner spin" />
              <i v-else class="pi pi-trash" />
              {{ t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useApi } from '@/composables/useApi'
import { useAuthStore } from '@/stores/useAuthStore'

const { t } = useI18n()
const api = useApi()
const auth = useAuthStore()

// ---------- Types ----------
interface Report {
  id: string
  simulation_id: string | null
  title: string
  status: 'generating' | 'ready' | 'failed'
  pdf_url: string | null
  share_token: string | null
  share_expires_at: string | null
  page_count: number | null
  file_size_bytes: number | null
  created_at: string
  updated_at: string
}

interface Simulation {
  id: string
  title: string
}

interface ReportsResponse {
  data: Report[]
  total: number
}

interface SimulationsResponse {
  data: Simulation[]
}

// ---------- State ----------
const reports = ref<Report[]>([])
const simulations = ref<Simulation[]>([])
const loading = ref(false)
const generating = ref(false)
const deleting = ref(false)
const showGenerateDialog = ref(false)
const deleteTarget = ref<Report | null>(null)

const isPro = computed(() => auth.isPro)

const toast = ref<{ visible: boolean; message: string; type: 'success' | 'error' }>({
  visible: false,
  message: '',
  type: 'success',
})

let toastTimeout: ReturnType<typeof setTimeout> | null = null

// ---------- Form ----------
const form = ref({
  title: '',
  simulation_id: '',
  report_type: 'market_overview',
  date_from: '',
  date_to: '',
})

const reportTypes = computed(() => [
  { value: 'market_overview', label: t('reports.types.marketOverview') },
  { value: 'supply_chain_risk', label: t('reports.types.supplyChainRisk') },
  { value: 'commodity_analysis', label: t('reports.types.commodityAnalysis') },
  { value: 'custom', label: t('reports.types.custom') },
])

// ---------- Functions ----------
function showToast(message: string, type: 'success' | 'error' = 'success') {
  if (toastTimeout) clearTimeout(toastTimeout)
  toast.value = { visible: true, message, type }
  toastTimeout = setTimeout(() => {
    toast.value.visible = false
  }, 3000)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

async function fetchReports() {
  loading.value = true
  try {
    const res = await api.get<ReportsResponse>('/reports')
    reports.value = res.data
  } catch (e) {
    console.error('Failed to fetch reports:', e)
    showToast(t('reports.fetchError'), 'error')
  } finally {
    loading.value = false
  }
}

async function fetchSimulations() {
  try {
    const res = await api.get<SimulationsResponse>('/simulations')
    simulations.value = res.data
  } catch {
    // Simulations are optional for the form — silent fail
  }
}

async function generateReport() {
  generating.value = true
  try {
    const body: Record<string, unknown> = {
      title: form.value.title.trim(),
      report_type: form.value.report_type,
    }
    if (form.value.simulation_id) body.simulation_id = form.value.simulation_id
    if (form.value.date_from) body.date_from = form.value.date_from
    if (form.value.date_to) body.date_to = form.value.date_to

    const newReport = await api.post<Report>('/reports', body)
    reports.value.unshift(newReport)
    showGenerateDialog.value = false
    form.value = { title: '', simulation_id: '', report_type: 'market_overview', date_from: '', date_to: '' }
    showToast(t('reports.generateSuccess'))

    // Poll for status updates if generating
    if (newReport.status === 'generating') {
      pollReportStatus(newReport.id)
    }
  } catch (e) {
    console.error('Failed to generate report:', e)
    showToast(t('reports.generateError'), 'error')
  } finally {
    generating.value = false
  }
}

async function pollReportStatus(reportId: string) {
  const maxAttempts = 30
  let attempts = 0

  const poll = async () => {
    attempts++
    try {
      const updated = await api.get<Report>(`/reports/${reportId}`)
      const idx = reports.value.findIndex(r => r.id === reportId)
      if (idx !== -1) reports.value[idx] = updated
      if (updated.status === 'generating' && attempts < maxAttempts) {
        setTimeout(poll, 5000)
      }
    } catch {
      // Silent — stop polling on error
    }
  }

  setTimeout(poll, 5000)
}

function downloadReport(report: Report) {
  if (report.pdf_url) {
    window.open(report.pdf_url, '_blank')
  }
}

async function shareReport(report: Report) {
  try {
    let token = report.share_token
    if (!token) {
      const res = await api.post<{ share_token: string }>(`/reports/${report.id}/share`)
      token = res.share_token
      const idx = reports.value.findIndex(r => r.id === report.id)
      if (idx !== -1) reports.value[idx].share_token = token
    }

    const shareUrl = `${window.location.origin}/shared/report/${token}`
    await navigator.clipboard.writeText(shareUrl)
    showToast(t('reports.shareCopied'))
  } catch (e) {
    console.error('Failed to share report:', e)
    showToast(t('reports.shareError'), 'error')
  }
}

function confirmDelete(report: Report) {
  deleteTarget.value = report
}

async function executeDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await api.del(`/reports/${deleteTarget.value.id}`)
    reports.value = reports.value.filter(r => r.id !== deleteTarget.value!.id)
    showToast(t('reports.deleteSuccess'))
    deleteTarget.value = null
  } catch (e) {
    console.error('Failed to delete report:', e)
    showToast(t('reports.deleteError'), 'error')
  } finally {
    deleting.value = false
  }
}

// ---------- Lifecycle ----------
onMounted(() => {
  fetchReports()
  fetchSimulations()
})
</script>

<style scoped>
.reports-view {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
  color: #f1f5f9;
  min-height: 100vh;
}

/* ---- Header ---- */
.reports-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-left h1 {
  font-size: 1.75rem;
  margin: 0;
  font-weight: 700;
}

.report-count-badge {
  background: #14b8a6;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  min-width: 28px;
  text-align: center;
}

/* ---- Buttons ---- */
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: #14b8a6;
  color: #fff;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #0d9488;
  box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary.btn-lg {
  padding: 0.75rem 1.75rem;
  font-size: 1rem;
  margin-top: 1.25rem;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: #1e293b;
  color: #94a3b8;
  border: 1px solid #334155;
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  border-color: #475569;
  color: #e2e8f0;
}

.btn-danger {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: #7f1d1d;
  color: #fca5a5;
  border: 1px solid #dc2626;
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-danger:hover:not(:disabled) {
  background: #991b1b;
}

.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---- Plan Banner ---- */
.plan-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1.25rem;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 10px;
  margin-bottom: 1.5rem;
  color: #fcd34d;
  font-size: 0.9rem;
}

.plan-upgrade-link {
  margin-left: auto;
  color: #14b8a6;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

.plan-upgrade-link:hover {
  color: #2dd4bf;
  text-decoration: underline;
}

/* ---- Reports Grid ---- */
.reports-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

/* ---- Report Card ---- */
.report-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s;
}

.report-card:hover {
  border-color: rgba(20, 184, 166, 0.3);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

.report-card-top {
  flex: 1;
}

.report-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.report-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
  line-height: 1.3;
  color: #f1f5f9;
}

/* ---- Status Badge ---- */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.65rem;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
  flex-shrink: 0;
}

.status-generating {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.status-ready {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

/* ---- Meta ---- */
.report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #64748b;
}

.meta-item i {
  font-size: 0.75rem;
}

.simulation-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #14b8a6;
  text-decoration: none;
  margin-bottom: 0.5rem;
  transition: color 0.2s;
}

.simulation-link:hover {
  color: #2dd4bf;
}

/* ---- Card Actions ---- */
.report-actions {
  display: flex;
  gap: 0.5rem;
  padding-top: 0.85rem;
  border-top: 1px solid #334155;
  margin-top: 0.85rem;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #334155;
  background: transparent;
  color: #94a3b8;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  border-color: #475569;
  color: #e2e8f0;
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.action-download:hover:not(:disabled) {
  border-color: #14b8a6;
  color: #14b8a6;
}

.action-share:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #3b82f6;
}

.action-delete {
  margin-left: auto;
}

.action-delete:hover:not(:disabled) {
  border-color: #ef4444;
  color: #ef4444;
}

/* ---- Toast ---- */
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 1.25rem;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 500;
  z-index: 9999;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.toast-success {
  background: #065f46;
  color: #6ee7b7;
  border: 1px solid #10b981;
}

.toast-error {
  background: #7f1d1d;
  color: #fca5a5;
  border: 1px solid #dc2626;
}

.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.3s ease;
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(40px);
}

/* ---- Dialog ---- */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.dialog-panel {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 16px;
  width: 100%;
  max-width: 520px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  animation: dialogSlideIn 0.25s ease-out;
}

.dialog-sm {
  max-width: 420px;
}

@keyframes dialogSlideIn {
  from {
    opacity: 0;
    transform: translateY(-16px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #334155;
}

.dialog-header h2 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0;
  color: #f1f5f9;
}

.dialog-close {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.dialog-close:hover {
  background: #334155;
  color: #e2e8f0;
}

.dialog-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid #334155;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

/* ---- Form ---- */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.form-input {
  background: #0f172a;
  border: 1px solid #334155;
  color: #f1f5f9;
  padding: 0.6rem 0.85rem;
  border-radius: 8px;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
  width: 100%;
  font-family: inherit;
}

.form-input:focus {
  border-color: #14b8a6;
}

.form-input::placeholder {
  color: #475569;
}

.form-input option {
  background: #0f172a;
  color: #f1f5f9;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

/* ---- Delete Dialog ---- */
.delete-message {
  color: #94a3b8;
  font-size: 0.95rem;
  line-height: 1.5;
  margin: 0;
}

/* ---- Empty State ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 2rem;
  text-align: center;
}

.empty-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(20, 184, 166, 0.08);
  border: 1px solid rgba(20, 184, 166, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.empty-icon {
  font-size: 2.25rem;
  color: #14b8a6;
}

.empty-state h3 {
  margin: 0 0 0.5rem;
  font-size: 1.2rem;
  color: #94a3b8;
  font-weight: 600;
}

.empty-state p {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
  max-width: 400px;
  line-height: 1.6;
}

/* ---- Skeleton ---- */
.skeleton-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.25rem;
}

.skeleton-bar {
  background: linear-gradient(90deg, #334155 25%, #3d4f66 50%, #334155 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.skeleton-title {
  width: 60%;
  height: 18px;
  margin-bottom: 1rem;
}

.skeleton-body {
  width: 80%;
  height: 12px;
  margin-bottom: 0.5rem;
}

.skeleton-meta {
  width: 50%;
  height: 10px;
  margin-bottom: 1rem;
}

.skeleton-actions {
  width: 40%;
  height: 32px;
  margin-top: 0.5rem;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

/* ---- Spinner ---- */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ---- Transitions ---- */
.report-list-enter-active,
.report-list-leave-active {
  transition: all 0.3s ease;
}

.report-list-enter-from {
  opacity: 0;
  transform: scale(0.95);
}

.report-list-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .reports-view {
    padding: 1rem;
  }

  .reports-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .reports-grid {
    grid-template-columns: 1fr;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  .dialog-panel {
    max-width: 100%;
    margin: 0.5rem;
  }

  .report-actions {
    flex-wrap: wrap;
  }

  .plan-banner {
    flex-direction: column;
    text-align: center;
  }

  .plan-upgrade-link {
    margin-left: 0;
  }
}
</style>
