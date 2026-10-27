// Local, device-only persistence so a participant can reload and revisit their
// last plan. The backend exposes no plan/credential endpoints, so nothing secret
// is stored here — only the inputs the user already typed and the public result.
import type { RecommendationResponse, ResolvedInterest } from '../types'

const STORAGE_KEY = 'common-thread.lastPlan.v2'

export type SavedParticipant = {
  participant_id: string
  display_name: string
  interests: string[]
  resolved_interests: ResolvedInterest[]
}

export type SavedPlan = {
  planRef: string
  savedAt: string
  location: string
  budget: string
  /** ISO 4217 code. Absent in plans saved before currencies existed (read as INR). */
  currency?: string
  participants: SavedParticipant[]
  result: RecommendationResponse | null
}

function isSavedParticipant(value: unknown): value is SavedParticipant {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  return (
    typeof v.participant_id === 'string' &&
    typeof v.display_name === 'string' &&
    Array.isArray(v.interests) &&
    Array.isArray(v.resolved_interests)
  )
}

export function savePlan(plan: SavedPlan): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(plan))
  } catch {
    // Storage may be unavailable (private mode, quota). Saving is best-effort.
  }
}

export function loadPlan(): SavedPlan | null {
  let raw: string | null = null
  try {
    raw = localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object') return null
    const candidate = parsed as Record<string, unknown>
    if (
      typeof candidate.planRef !== 'string' ||
      typeof candidate.location !== 'string' ||
      typeof candidate.budget !== 'string' ||
      (candidate.currency !== undefined && typeof candidate.currency !== 'string') ||
      !Array.isArray(candidate.participants) ||
      !candidate.participants.every(isSavedParticipant)
    ) {
      return null
    }
    return parsed as SavedPlan
  } catch {
    // Corrupted/partial JSON: treat as no saved plan rather than crashing.
    return null
  }
}

export function clearPlan(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

/** Human-friendly local plan reference (not a credential, not server-issued). */
export function newPlanRef(): string {
  return `CT-${Date.now().toString(36).toUpperCase()}`
}
