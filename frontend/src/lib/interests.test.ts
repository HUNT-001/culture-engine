import { describe, expect, it } from 'vitest'
import type { EntityCandidate } from '../types'
import {
  buildInterestPayload, newRow, rowStatus, rowsFromSaved, unconfirmedCount,
  validateInterestRows, type InterestRow,
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
})

describe('validateInterestRows', () => {
  it('requires at least one non-blank interest', () => {
    expect(validateInterestRows([row('   ')])).toHaveLength(1)
    expect(validateInterestRows([row('jazz')])).toEqual([])
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
