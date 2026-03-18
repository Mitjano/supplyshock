import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/useAuthStore'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const dailyUsed = ref(0)
  const dailyLimit = ref<number | null>(null)
  const error = ref<string | null>(null)

  const hasMessages = computed(() => messages.value.length > 0)
  const usageText = computed(() => {
    if (dailyLimit.value === null) return null
    return `${dailyUsed.value}/${dailyLimit.value}`
  })

  function addMessage(role: 'user' | 'assistant', content: string): ChatMessage {
    const msg: ChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
      timestamp: new Date(),
    }
    messages.value.push(msg)
    return msg
  }

  async function sendMessage(text: string) {
    if (!text.trim() || loading.value) return
    error.value = null

    addMessage('user', text.trim())
    const assistantMsg = addMessage('assistant', '')
    loading.value = true

    try {
      const auth = useAuthStore()
      const token = await auth.getToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: text.trim() }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        const detail = typeof err.detail === 'string' ? err.detail : err.detail?.error || 'Request failed'
        throw new Error(detail)
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response stream')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)

          try {
            const data = JSON.parse(jsonStr)

            if (data.type === 'meta') {
              dailyUsed.value = data.used ?? 0
              dailyLimit.value = data.limit ?? null
            } else if (data.type === 'token') {
              assistantMsg.content += data.content
            } else if (data.type === 'error') {
              error.value = data.message
            }
            // 'done' — no action needed
          } catch {
            // Skip malformed JSON lines
          }
        }
      }

      // If the assistant message is still empty after stream, mark error
      if (!assistantMsg.content) {
        error.value = error.value || 'No response received'
        // Remove the empty assistant message
        messages.value = messages.value.filter(m => m.id !== assistantMsg.id)
      }
    } catch (e: any) {
      error.value = e.message || 'An error occurred'
      // Remove the empty assistant message on failure
      if (!assistantMsg.content) {
        messages.value = messages.value.filter(m => m.id !== assistantMsg.id)
      }
    } finally {
      loading.value = false
    }
  }

  function clearMessages() {
    messages.value = []
    error.value = null
  }

  return {
    messages,
    loading,
    dailyUsed,
    dailyLimit,
    error,
    hasMessages,
    usageText,
    sendMessage,
    clearMessages,
  }
})
