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

/** Build the API payload: typed texts + the confirmed-entity overlay. */
export function buildInterestPayload(
  rows: InterestRow[],
): { interests: string[]; resolved_interests: ResolvedInterest[] } {
  const interests: string[] = []
  const resolved: ResolvedInterest[] = []
  const seen = new Set<string>()
  for (const row of rows) {
    const text = row.text.trim()
    if (!text) continue
    const key = text.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    interests.push(text)
    if (row.selected) {
      resolved.push({
        text,
        entity_id: row.selected.entity_id,
        name: row.selected.name,
        entity_type: row.selected.entity_type,
      })
    }
    if (interests.length >= MAX_INTERESTS) break
  }
  return { interests, resolved_interests: resolved }
}

export function validateInterestRows(rows: InterestRow[]): string[] {
  const { interests } = buildInterestPayload(rows)
  const errors: string[] = []
  if (interests.length === 0) {
    errors.push('Add at least one interest (letters or words, not just spaces or commas).')
  }
  return errors
}

export type RowStatus = 'empty' | 'unconfirmed' | 'confirmed'

export function rowStatus(row: InterestRow): RowStatus {
  if (!row.text.trim()) return 'empty'
  return row.selected ? 'confirmed' : 'unconfirmed'
}

/** How many typed interests are not yet confirmed (used for gentle guidance, not blocking). */
export function unconfirmedCount(rows: InterestRow[]): number {
  return rows.filter((r) => rowStatus(r) === 'unconfirmed').length
}
