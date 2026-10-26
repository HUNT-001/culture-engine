import { describe, expect, it } from 'vitest'
import type { EntityCandidate } from '../types'
import {
  buildInterestPayload, newRow, rowStatus, rowsFromSaved, submittedRows, unconfirmedCount,
  unconfirmedSavedInterests, validateInterestRows, type InterestRow,
} from './interests'

function candidate(over: Partial<EntityCandidate> = {}): EntityCandidate {
  return { entity_id: 'E1', name: 'Indie Rock', entity_type: 'urn:tag', source: 'qloo', ...over }
}
function row(text: string, selected: EntityCandidate | null = null): InterestRow {
  return { ...newRow(text), selected }
}

describe('buildInterestPayload', () => {
  it('collects typed texts and only confirmed selections', () => {
    const rows = [row('indie rock', candidate()), row('jazz'), row('  ')]
    const payload = buildInterestPayload(rows)
    expect(payload.interests).toEqual(['indie rock', 'jazz'])
    expect(payload.resolved_interests).toEqual([
      { text: 'indie rock', entity_id: 'E1', name: 'Indie Rock', entity_type: 'urn:tag' },
    ])
  })

  it('trims, de-duplicates and caps at three', () => {
    const rows = [row('A'), row('a'), row('B'), row('C'), row('D')]
    expect(buildInterestPayload(rows).interests).toEqual(['A', 'B', 'C'])
  })

  it('never emits a resolved interest without a selection (no fabrication)', () => {
    expect(buildInterestPayload([row('jazz')]).resolved_interests).toEqual([])
  })

  it('keeps the confirmed entity id and the typed wording exactly as picked', () => {
    const homonym = candidate({ entity_id: 'band:phoenix', name: 'Phoenix', entity_type: 'urn:entity:artist' })
    const payload = buildInterestPayload([row('  PHOENIX ', homonym)])
    expect(payload.interests).toEqual(['PHOENIX'])             // wording kept (trimmed only)
    expect(payload.resolved_interests).toEqual([
      { text: 'PHOENIX', entity_id: 'band:phoenix', name: 'Phoenix', entity_type: 'urn:entity:artist' },
    ])
  })

  it('prefers the confirmed row when a duplicate phrase is also present unconfirmed', () => {
    const rows = [row('Jazz'), row('jazz', candidate({ entity_id: 'J1', name: 'Jazz' }))]
    const payload = buildInterestPayload(rows)
    expect(payload.interests).toEqual(['jazz'])
    expect(payload.resolved_interests.map((r) => r.entity_id)).toEqual(['J1'])
    expect(validateInterestRows(rows)).toEqual([])
  })

  it('submitted rows and the payload always agree', () => {
    const rows = [row('A', candidate()), row('a'), row('B'), row('C', candidate()), row('D')]
    expect(submittedRows(rows).map((r) => r.text)).toEqual(buildInterestPayload(rows).interests)
  })
})

describe('validateInterestRows (shared by the Quick and Collaborative flows)', () => {
  it('requires at least one non-blank interest', () => {
    expect(validateInterestRows([row('   ')])).toHaveLength(1)
    expect(validateInterestRows([])).toHaveLength(1)
  })

  it('accepts only interests the user explicitly confirmed', () => {
    expect(validateInterestRows([row('jazz', candidate())])).toEqual([])
  })

  it('blocks an unconfirmed interest, even when its text would match an entity name exactly', () => {
    // "Indie Rock" is typed exactly as the candidate name, but never picked: still blocked.
    const errors = validateInterestRows([row('Indie Rock')])
    expect(errors).toHaveLength(1)
    expect(errors[0]).toContain('Indie Rock')
  })

  it('names every unconfirmed interest, and ignores blank rows', () => {
    const errors = validateInterestRows([row('jazz', candidate()), row('phoenix'), row(''), row('pulp')])
    expect(errors).toHaveLength(2)
    expect(errors[0]).toContain('phoenix')
    expect(errors[1]).toContain('pulp')
  })

  it('does not count a candidate list that was searched but not picked as a confirmation', () => {
    const searched: InterestRow = { ...newRow('phoenix'), searched: true, candidates: [candidate()] }
    expect(validateInterestRows([searched])).toHaveLength(1)
  })

  it('a removed (blank) unconfirmed row no longer blocks', () => {
    expect(validateInterestRows([row('jazz', candidate()), row('')])).toEqual([])
  })
})

describe('rowStatus / unconfirmedCount', () => {
  it('classifies rows', () => {
    expect(rowStatus(row(''))).toBe('empty')
    expect(rowStatus(row('jazz'))).toBe('unconfirmed')
    expect(rowStatus(row('jazz', candidate()))).toBe('confirmed')
    expect(unconfirmedCount([row('jazz'), row('x', candidate()), row('')])).toBe(1)
  })
})

describe('unconfirmedSavedInterests', () => {
  it('lists saved interests with no confirmed entity (case/space-insensitive match)', () => {
    const resolved = [{ text: 'Jazz', entity_id: 'J1', name: 'Jazz', entity_type: 'urn:tag' }]
    expect(unconfirmedSavedInterests(['jazz ', 'opera'], resolved)).toEqual(['opera'])
    expect(unconfirmedSavedInterests([], [])).toEqual([])
  })
})

describe('rowsFromSaved', () => {
  it('restores confirmed selections by matching text', () => {
    const rows = rowsFromSaved(
      ['independent film', 'jazz'],
      [{ text: 'independent film', entity_id: 'F1', name: 'Independent Film', entity_type: 'urn:tag' }],
    )
    expect(rows).toHaveLength(2)
    expect(rows[0].selected?.entity_id).toBe('F1')
    expect(rows[1].selected).toBeNull() // jazz was not confirmed
  })

  it('returns a single empty row when there is nothing saved', () => {
    const rows = rowsFromSaved([], [])
    expect(rows).toHaveLength(1)
    expect(rows[0].text).toBe('')
  })
})

describe('editing and revisiting', () => {
  it('a confirmation restored on revisit still satisfies validation and is re-sent unchanged', () => {
    const saved = [{ text: 'phoenix', entity_id: 'band:phoenix', name: 'Phoenix', entity_type: 'urn:entity:artist' }]
    const rows = rowsFromSaved(['phoenix'], saved)
    expect(validateInterestRows(rows)).toEqual([])
    expect(buildInterestPayload(rows).resolved_interests[0].entity_id).toBe('band:phoenix')
  })

  it('a saved interest with no confirmation comes back unconfirmed and blocks until picked', () => {
    const rows = rowsFromSaved(['phoenix'], [])
    expect(rowStatus(rows[0])).toBe('unconfirmed')
    expect(validateInterestRows(rows)).toHaveLength(1)
  })

  it('changing the typed text drops the old confirmation (as the picker does on edit)', () => {
    const confirmed = row('phoenix', candidate({ entity_id: 'band:phoenix' }))
    const edited: InterestRow = { ...confirmed, text: 'phoenix rising', candidates: [], selected: null, searched: false }
    expect(validateInterestRows([edited])).toHaveLength(1)
    expect(buildInterestPayload([edited]).resolved_interests).toEqual([])
  })
})
