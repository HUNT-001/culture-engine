// Pure model for interest rows with per-interest confirmation state.
import type { EntityCandidate, ResolvedInterest } from '../types'

export const MAX_INTERESTS = 3

export type InterestRow = {
  id: string
  text: string
  candidates: EntityCandidate[]
  selected: EntityCandidate | null
  searched: boolean // a search has been run for the current text
}

let counter = 0
export function newRow(text = ''): InterestRow {
  counter += 1
  return { id: `ir-${Date.now().toString(36)}-${counter}`, text, candidates: [], selected: null, searched: false }
}

/** Rebuild rows from a participant's saved interests + confirmed selections (for revisit). */
export function rowsFromSaved(interests: string[], resolved: ResolvedInterest[]): InterestRow[] {
  const byText = new Map(resolved.map((r) => [r.text.trim().toLowerCase(), r]))
  const rows = interests.slice(0, MAX_INTERESTS).map((text) => {
    const row = newRow(text)
    const match = byText.get(text.trim().toLowerCase())
    if (match) {
      row.selected = {
        entity_id: match.entity_id, name: match.name, entity_type: match.entity_type, source: 'qloo',
      }
    }
    return row
  })
  return rows.length ? rows : [newRow()]
}

/** The rows that will actually be submitted: trimmed, de-duplicated (case-insensitive,
 *  preferring a confirmed row over an unconfirmed duplicate), capped at three. */
export function submittedRows(rows: InterestRow[]): InterestRow[] {
  const order: string[] = []
  const byKey = new Map<string, InterestRow>()
  for (const row of rows) {
    const text = row.text.trim()
    if (!text) continue
    const key = text.toLowerCase()
    const existing = byKey.get(key)
    if (!existing) {
      order.push(key)
      byKey.set(key, row)
    } else if (!existing.selected && row.selected) {
      byKey.set(key, row)
    }
  }
  return order.slice(0, MAX_INTERESTS).map((key) => byKey.get(key) as InterestRow)
}

/** Build the API payload: the user's own typed wording + the confirmed-entity overlay.
 *  An entity is attached only when the user explicitly picked it; nothing is inferred. */
export function buildInterestPayload(
  rows: InterestRow[],
): { interests: string[]; resolved_interests: ResolvedInterest[] } {
  const interests: string[] = []
  const resolved: ResolvedInterest[] = []
  for (const row of submittedRows(rows)) {
    const text = row.text.trim()
    interests.push(text)
    if (row.selected) {
      resolved.push({
        text,
        entity_id: row.selected.entity_id,
        name: row.selected.name,
        entity_type: row.selected.entity_type,
      })
    }
  }
  return { interests, resolved_interests: resolved }
}

/** Blocking validation shared by the Quick and Collaborative flows. Every non-empty interest
 *  must be confirmed to a specific entity (or removed): the server never guesses one. */
export function validateInterestRows(rows: InterestRow[]): string[] {
  const submitted = submittedRows(rows)
  if (submitted.length === 0) {
    return ['Add at least one interest (letters or words, not just spaces or commas).']
  }
  return submitted
    .filter((row) => !row.selected)
    .map((row) => `Confirm which entity you mean for “${row.text.trim()}” — search and pick one, or remove it.`)
}

export type RowStatus = 'empty' | 'unconfirmed' | 'confirmed'

export function rowStatus(row: InterestRow): RowStatus {
  if (!row.text.trim()) return 'empty'
  return row.selected ? 'confirmed' : 'unconfirmed'
}

/** How many typed interests are not yet confirmed (these block submission). */
export function unconfirmedCount(rows: InterestRow[]): number {
  return rows.filter((r) => rowStatus(r) === 'unconfirmed').length
}

/** Saved interests of a participant that have no confirmed entity (e.g. saved before
 *  confirmation was required). The server leaves these out of a run and says so. */
export function unconfirmedSavedInterests(
  interests: string[], resolved: ResolvedInterest[],
): string[] {
  const confirmed = new Set(resolved.map((r) => r.text.trim().toLowerCase()))
  return interests.filter((t) => !confirmed.has(t.trim().toLowerCase()))
}
