import { describe, expect, it } from 'vitest'
import {
  buildPayload, newParticipantId, normalizeInterests, validatePlan, type DraftParticipant,
} from './plan'

function draft(overrides: Partial<DraftParticipant> = {}): DraftParticipant {
  return { participant_id: newParticipantId(), display_name: 'Ana', interestsText: 'jazz', ...overrides }
}

describe('normalizeInterests', () => {
  it('trims, drops blanks, and de-duplicates case-insensitively', () => {
    expect(normalizeInterests('  jazz ,, Jazz , film  ')).toEqual(['jazz', 'film'])
  })
  it('rejects whitespace/comma-only input', () => {
    expect(normalizeInterests('   ')).toEqual([])
    expect(normalizeInterests(' , , ')).toEqual([])
  })
  it('caps at three interests', () => {
    expect(normalizeInterests('a, b, c, d, e')).toEqual(['a', 'b', 'c'])
  })
})

describe('validatePlan', () => {
  const two = [draft({ display_name: 'Ana', interestsText: 'jazz' }),
               draft({ display_name: 'Ben', interestsText: 'anime' })]

  it('accepts a well-formed plan', () => {
    expect(validatePlan('Austin, Texas', '800', two).ok).toBe(true)
  })
  it('flags a short location', () => {
    const result = validatePlan('A', '', two)
    expect(result.ok).toBe(false)
    expect(result.errors.some((e) => e.toLowerCase().includes('location'))).toBe(true)
  })
  it('flags an invalid budget but allows a blank one', () => {
    expect(validatePlan('Austin', '-5', two).ok).toBe(false)
    expect(validatePlan('Austin', '', two).ok).toBe(true)
  })
  it('requires at least two participants', () => {
    expect(validatePlan('Austin', '', [draft()]).ok).toBe(false)
  })
  it('requires each participant to have a resolvable interest', () => {
    const bad = [draft({ display_name: 'Ana', interestsText: 'jazz' }),
                 draft({ display_name: 'Ben', interestsText: '   ' })]
    const result = validatePlan('Austin', '', bad)
    expect(result.ok).toBe(false)
    expect(result.errors.some((e) => e.includes('Ben') && e.includes('interest'))).toBe(true)
  })
  it('names a participant that is missing a display name', () => {
    const bad = [draft({ display_name: '  ', interestsText: 'jazz' }), draft({ display_name: 'Ben' })]
    expect(validatePlan('Austin', '', bad).errors.some((e) => e.includes('Participant 1'))).toBe(true)
  })
})

describe('buildPayload', () => {
  it('produces the exact backend request shape with normalised interests', () => {
    const payload = buildPayload('  Austin  ', '800', [
      draft({ display_name: ' Ana ', interestsText: 'jazz, jazz, film' }),
      draft({ display_name: 'Ben', interestsText: 'anime' }),
    ])
    expect(payload.location).toBe('Austin')
    expect(payload.budget_per_person).toBe(800)
    expect(payload.participants[0].display_name).toBe('Ana')
    expect(payload.participants[0].interests).toEqual(['jazz', 'film'])
  })
  it('omits budget when blank or non-positive', () => {
    expect(buildPayload('Austin', '', [draft(), draft()]).budget_per_person).toBeUndefined()
    expect(buildPayload('Austin', '0', [draft(), draft()]).budget_per_person).toBeUndefined()
  })
})
