import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '@/composables/useApi'

export interface AlertEvent {
  id: string
  time: string
  type: string
  severity: string
  title: string
  body: string
  commodity: string | null
  region: string | null
  source: string | null
  source_url: string | null
  is_active: boolean
  is_read?: boolean
  snoozed_until?: string | null
}

export const useAlertStore = defineStore('alerts', () => {
  const api = useApi()
  const alerts = ref<AlertEvent[]>([])
  const loading = ref(false)
  const total = ref(0)

  // Filters
  const severityFilter = ref<string | null>(null)
  const typeFilter = ref<string | null>(null)
  const unreadOnly = ref(false)

  const unreadCount = computed(() => alerts.value.filter(a => !a.is_read).length)

  async function fetchAlerts(params?: Record<string, string>) {
    loading.value = true
    try {
      const query: Record<string, string> = { ...params }
      if (severityFilter.value) query.severity = severityFilter.value
      if (typeFilter.value) query.type = typeFilter.value
      if (unreadOnly.value) query.unread = 'true'

      const res = await api.get<{ data: AlertEvent[]; meta: { total: number } }>('/alerts', query)
      alerts.value = res.data
      total.value = res.meta.total
    } catch (e) {
      console.error('Failed to fetch alerts:', e)
    } finally {
      loading.value = false
    }
  }

  async function markAsRead(alertId: string) {
    try {
      await api.post(`/alerts/${alertId}/read`)
      const alert = alerts.value.find(a => a.id === alertId)
      if (alert) alert.is_read = true
    } catch (e) {
      console.error('Failed to mark alert as read:', e)
    }
  }

  async function snoozeAlert(alertId: string, hours: number = 4) {
    try {
      await api.post(`/alerts/${alertId}/snooze?hours=${hours}`)
      alerts.value = alerts.value.filter(a => a.id !== alertId)
    } catch (e) {
      console.error('Failed to snooze alert:', e)
    }
  }

  async function bulkMarkRead(ids?: string[]) {
    try {
      const query = ids ? `?alert_ids=${ids.join(',')}` : ''
      await api.post(`/alerts/bulk/read${query}`)
      if (ids) {
        alerts.value.forEach(a => { if (ids.includes(a.id)) a.is_read = true })
      } else {
        alerts.value.forEach(a => { a.is_read = true })
      }
    } catch (e) {
      console.error('Failed to bulk mark read:', e)
    }
  }

  return {
    alerts,
    loading,
    total,
    severityFilter,
    typeFilter,
    unreadOnly,
    unreadCount,
    fetchAlerts,
    markAsRead,
    snoozeAlert,
    bulkMarkRead,
  }
})
