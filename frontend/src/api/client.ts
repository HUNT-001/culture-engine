import type {
  EntitySearchResponse, JoinPlanResponse, ParticipantView, PlanCreatedResponse, PlanView,
  RecommendationRequest, RecommendationResponse, ResolvedInterest,
} from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/$/, '')

export type HealthResponse = { status: string; environment?: string; demo_mode: boolean }

const NETWORK_MESSAGE =
  'Could not reach the backend. Check that the API is running (and, on a free tier, give it a moment to wake up).'

/** Carries the HTTP status so the UI can distinguish 401 / 404 / 409 / 410 / 422 states. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

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
      const messages = detail
        .map((item) => (item && typeof item === 'object' ? (item as Record<string, unknown>).msg : null))
        .filter((msg): msg is string => typeof msg === 'string')
      if (messages.length) return `Please check your inputs: ${messages.join('; ')}.`
    }
  }
  return `Request failed (${status}). Please try again.`
}

type RequestOptions = {
  method?: string
  body?: unknown
  // Header-based credentials only. Tokens never go in the URL/query string.
  shareToken?: string
  participantToken?: string
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.shareToken) headers['X-Share-Token'] = options.shareToken
  if (options.participantToken) headers['X-Participant-Token'] = options.participantToken

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
  } catch {
    // Network/DNS/CORS failure before any HTTP status.
    throw new ApiError(0, NETWORK_MESSAGE)
  }
  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}))
    throw new ApiError(response.status, readErrorDetail(errBody, response.status))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

// --- Health + stateless flow (unchanged fallback) ---

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export async function getRecommendations(payload: RecommendationRequest): Promise<RecommendationResponse> {
  return request<RecommendationResponse>('/recommendations', { method: 'POST', body: payload })
}

export async function searchEntities(query: string, take = 5): Promise<EntitySearchResponse> {
  const q = encodeURIComponent(query.trim())
  return request<EntitySearchResponse>(`/entities/search?query=${q}&take=${take}`)
}

// --- Group plan lifecycle ---

export function createPlan(
  input: { location: string; budget_per_person?: number; budget_currency?: string },
): Promise<PlanCreatedResponse> {
  return request<PlanCreatedResponse>('/plans', { method: 'POST', body: input })
}

export function getPlan(planId: string, shareToken: string): Promise<PlanView> {
  return request<PlanView>(`/plans/${encodeURIComponent(planId)}`, { shareToken })
}

export function joinPlan(planId: string, shareToken: string, displayName: string): Promise<JoinPlanResponse> {
  return request<JoinPlanResponse>(`/plans/${encodeURIComponent(planId)}/participants`, {
    method: 'POST', shareToken, body: { display_name: displayName },
  })
}

export function setPreferences(
  planId: string, participantId: string, participantToken: string,
  prefs: { interests: string[]; resolved_interests?: ResolvedInterest[]; dislikes: string[] },
): Promise<ParticipantView> {
  return request<ParticipantView>(
    `/plans/${encodeURIComponent(planId)}/participants/${encodeURIComponent(participantId)}/preferences`,
    { method: 'PUT', participantToken, body: prefs },
  )
}

export function runPlanRecommendations(planId: string, shareToken: string): Promise<RecommendationResponse> {
  return request<RecommendationResponse>(`/plans/${encodeURIComponent(planId)}/recommendations`, {
    method: 'POST', shareToken,
  })
}
