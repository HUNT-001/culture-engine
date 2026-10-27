import { describe, expect, it } from 'vitest'

// Source-level guard: the Quick and Collaborative flows must use the same confirmation gate,
// and no screen may promise that exact matches are accepted automatically.
const sources = import.meta.glob('../components/*.tsx', {
  query: '?raw', import: 'default', eager: true,
}) as Record<string, string>

const quick = sources['../components/QuickPlanner.tsx']
const collaborative = sources['../components/CollaborativePlanner.tsx']

describe('Quick and Collaborative flows share one confirmation behaviour', () => {
  it('both gate submission on validateInterestRows and send buildInterestPayload', () => {
    for (const source of [quick, collaborative]) {
      expect(source).toBeTruthy()
      expect(source).toMatch(/validateInterestRows\(/)
      expect(source).toMatch(/buildInterestPayload\(/)
      expect(source).toMatch(/from '\.\.\/lib\/interests'/)
    }
  })

  it('both collect interests through the same InterestPicker', () => {
    expect(quick).toMatch(/<InterestPicker/)
    expect(collaborative).toMatch(/<InterestPicker/)
  })

  it('no screen tells the user that exact matches are accepted automatically', () => {
    for (const [file, source] of Object.entries(sources)) {
      expect(source, file).not.toMatch(/auto-accept/i)
      expect(source, file).not.toMatch(/leave (it )?as typed/i)
    }
  })
})
