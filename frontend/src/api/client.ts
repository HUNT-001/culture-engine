import type { RecommendationRequest, RecommendationResponse } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/$/, '')

export async function getHealth(): Promise<{ status: string; demo_mode: boolean }> {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) throw new Error('Backend is not ready yet.')
  return response.json()
}

export async function getRecommendations(payload: RecommendationRequest): Promise<RecommendationResponse> {
  const response = await fetch(`${API_BASE}/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message
    throw new Error(detail || `Request failed (${response.status}). Please try again.`)
  }
  return response.json()
}
