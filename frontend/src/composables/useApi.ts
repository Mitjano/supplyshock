import { useAuthStore } from '@/stores/useAuthStore'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export function useApi() {
  const auth = useAuthStore()

  async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${API_BASE}${path}`)
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))

    const token = await auth.getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch(url.toString(), { headers })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, error.detail || 'Request failed')
    }

    return res.json()
  }

  async function post<T>(path: string, body?: unknown): Promise<T> {
    const token = await auth.getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers,
      body: body ? JSON.stringify(body) : undefined
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, error.detail || 'Request failed')
    }

    return res.json()
  }

  return { get, post }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}
