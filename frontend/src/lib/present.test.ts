import { describe, expect, it } from 'vitest'
import { barPercent, coverageDots, friendlyType, initials } from './present'

describe('friendlyType', () => {
  it('turns Qloo urns into readable labels', () => {
    expect(friendlyType('urn:entity:artist')).toBe('Artist')
    expect(friendlyType('urn:entity:place')).toBe('Place')
    expect(friendlyType('urn:tag:genre:media')).toBe('Tag · Genre media')
    expect(friendlyType('demo:entity')).toBe('Demo entity')
  })
  it('returns null when there is nothing meaningful to show', () => {
    expect(friendlyType(undefined)).toBeNull()
    expect(friendlyType(null)).toBeNull()
    expect(friendlyType('')).toBeNull()
    expect(friendlyType('unknown')).toBeNull()
  })
})

describe('initials', () => {
  it('uses first and last word, upper-cased', () => {
    expect(initials('asha')).toBe('A')
    expect(initials('Asha Rao')).toBe('AR')
    expect(initials('  ben   van  der Berg ')).toBe('BB')
  })
  it('falls back to a placeholder for blank names', () => {
    expect(initials('   ')).toBe('?')
  })
})

describe('barPercent', () => {
  it('maps 0–1 to a clamped percentage', () => {
    expect(barPercent(0.914)).toBe(91)
    expect(barPercent(1.7)).toBe(100)
    expect(barPercent(-0.2)).toBe(0)
  })
  it('is null for missing or non-finite values (never a made-up bar)', () => {
    expect(barPercent(undefined)).toBeNull()
    expect(barPercent(null)).toBeNull()
    expect(barPercent(Number.NaN)).toBeNull()
    expect(barPercent(Number.POSITIVE_INFINITY)).toBeNull()
  })
})

describe('coverageDots', () => {
  it('fills one dot per covered participant', () => {
    expect(coverageDots(2, 3)).toEqual([true, true, false])
    expect(coverageDots(0, 2)).toEqual([false, false])
  })
  it('stays sensible when the participant count is unknown or smaller', () => {
    expect(coverageDots(2, 0)).toEqual([true, true])
    expect(coverageDots(3, 2)).toEqual([true, true, true])
  })
})
