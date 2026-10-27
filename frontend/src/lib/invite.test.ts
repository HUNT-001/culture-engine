import { describe, expect, it } from 'vitest'
import { cleanCode, formatInviteText, hoursUntil, isExpired, validateJoinInput } from './invite'

describe('invite helpers', () => {
  it('cleanCode trims surrounding whitespace', () => {
    expect(cleanCode('  abc  ')).toBe('abc')
  })

  it('formatInviteText contains both the plan id and share code, as text (no URL)', () => {
    const text = formatInviteText('plan-123', 'secret-code')
    expect(text).toContain('plan-123')
    expect(text).toContain('secret-code')
    expect(text).not.toMatch(/https?:\/\//) // never embed the token in a link
  })

  it('validateJoinInput flags missing plan id and share code', () => {
    expect(validateJoinInput('', '')).toHaveLength(2)
    expect(validateJoinInput('plan', '')).toHaveLength(1)
    expect(validateJoinInput('plan', 'code')).toEqual([])
    expect(validateJoinInput('  ', '  ')).toHaveLength(2)
  })

  it('hoursUntil floors remaining hours and never goes negative', () => {
    const now = new Date('2026-01-01T00:00:00Z')
    expect(hoursUntil('2026-01-01T05:30:00Z', now)).toBe(5)
    expect(hoursUntil('2025-12-31T00:00:00Z', now)).toBe(0)
    expect(hoursUntil('not-a-date', now)).toBeNull()
  })

  it('isExpired reflects the timestamp', () => {
    const now = new Date('2026-01-01T00:00:00Z')
    expect(isExpired('2025-12-31T23:59:59Z', now)).toBe(true)
    expect(isExpired('2026-01-01T01:00:00Z', now)).toBe(false)
    expect(isExpired('garbage', now)).toBe(false)
  })
})
