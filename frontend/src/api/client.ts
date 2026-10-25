import type { RecommendationRequest, RecommendationResponse } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/$/, '')

export type HealthResponse = { status: string; environment?: string; demo_mode: boolean }

const NETWORK_MESSAGE =
  'Could not reach the backend. Check that the API is running (and, on a free tier, give it a moment to wake up).'

/** Extract a human-readable message from a FastAPI error body without leaking internals. */
function readErrorDetail(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const detail = (body as Record<string, unknown>).detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const message = (detail as Record<string, unknown>).message
      if (typeof message === 'string') return message
    }
    if (Array.isArray(detail)) {
      // 422 validation errors: [{ loc, msg, type }, ...]
      const messages = detail
        .map((item) => (item && typeof item === 'object' ? (item as Record<string, unknown>).msg : null))
        .filter((msg): msg is string => typeof msg === 'string')
      if (messages.length) return `Please check your inputs: ${messages.join('; ')}.`
    }
  }
  return `Request failed (${status}). Please try again.`
}

export async function getHealth(): Promise<HealthResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/health`)
  } catch {
    throw new Error(NETWORK_MESSAGE)
  }
  if (!response.ok) throw new Error('Backend is not ready yet.')
  return response.json()
}

export async function getRecommendations(payload: RecommendationRequest): Promise<RecommendationResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    // fetch rejects (TypeError) on network/DNS/CORS failure before any HTTP status.
    throw new Error(NETWORK_MESSAGE)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(readErrorDetail(body, response.status))
  }
  return response.json()
}
