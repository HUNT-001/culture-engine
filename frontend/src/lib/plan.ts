// Pure, framework-free helpers for building and validating a group plan.
// Kept separate from React so they can be unit-tested without a DOM.
import type { RecommendationRequest } from '../types'

export type DraftParticipant = {
  participant_id: string
  display_name: string
  // Raw, user-typed interests (comma-separated); normalised at submit time.
  interestsText: string
}

export const MIN_PARTICIPANTS = 2
export const MAX_PARTICIPANTS = 4
export const MAX_INTERESTS = 3

/** Trim, drop empties, and de-duplicate (case-insensitive) interest terms. */
export function normalizeInterests(raw: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const part of raw.split(',')) {
    const term = part.trim()
    if (!term) continue
    const key = term.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(term)
    if (out.length >= MAX_INTERESTS) break
  }
  return out
}

export type ValidationResult = { ok: boolean; errors: string[] }

/** Mirror the backend's validation so the user gets fast, specific feedback. */
export function validatePlan(
  location: string,
  budget: string,
  participants: DraftParticipant[],
): ValidationResult {
  const errors: string[] = []

  const loc = location.trim()
  if (loc.length < 2) {
    errors.push('Enter a location (at least 2 characters) so we know where to search.')
  } else if (loc.length > 160) {
    errors.push('Location is too long (max 160 characters).')
  }

  if (budget.trim()) {
    const value = Number(budget)
    if (!Number.isFinite(value) || value <= 0) {
      errors.push('Budget must be a positive number, or leave it blank.')
    } else if (value > 100000) {
      errors.push('Budget looks too large (max 100000). Leave it blank if unsure.')
    }
  }

  if (participants.length < MIN_PARTICIPANTS) {
    errors.push(`Add at least ${MIN_PARTICIPANTS} participants — Common Thread looks for overlap across a group.`)
  }
  if (participants.length > MAX_PARTICIPANTS) {
    errors.push(`This prototype supports up to ${MAX_PARTICIPANTS} participants.`)
  }

  const ids = new Set<string>()
  participants.forEach((person, index) => {
    const name = person.display_name.trim()
    const label = name || `Participant ${index + 1}`
    if (!name) {
      errors.push(`Participant ${index + 1} needs a name.`)
    }
    if (ids.has(person.participant_id)) {
      errors.push(`${label} has a duplicate id; remove and re-add them.`)
    }
    ids.add(person.participant_id)
    if (normalizeInterests(person.interestsText).length === 0) {
      errors.push(`${label} needs at least one interest — letters or words, not just spaces or commas.`)
    }
  })

  return { ok: errors.length === 0, errors }
}

/** Build the exact POST /api/recommendations body from draft state. */
export function buildPayload(
  location: string,
  budget: string,
  participants: DraftParticipant[],
): RecommendationRequest {
  const payload: RecommendationRequest = {
    location: location.trim(),
    participants: participants.map((person) => ({
      participant_id: person.participant_id,
      display_name: person.display_name.trim(),
      interests: normalizeInterests(person.interestsText),
    })),
  }
  const value = Number(budget)
  if (budget.trim() && Number.isFinite(value) && value > 0) {
    payload.budget_per_person = value
  }
  return payload
}

let counter = 0
/** Local, non-secret participant id. The backend has no accounts in this build. */
export function newParticipantId(): string {
  counter += 1
  return `p-${Date.now().toString(36)}-${counter}`
}
