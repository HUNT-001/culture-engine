import { beforeEach, describe, expect, it } from 'vitest'
import { clearSession, loadSession, saveSession, type DeviceSession } from './session'

class MemoryStorage {
  private store = new Map<string, string>()
  getItem(k: string) { return this.store.has(k) ? this.store.get(k)! : null }
  setItem(k: string, v: string) { this.store.set(k, v) }
  removeItem(k: string) { this.store.delete(k) }
}

beforeEach(() => {
  ;(globalThis as unknown as { sessionStorage: MemoryStorage }).sessionStorage = new MemoryStorage()
})

const base: DeviceSession = { planId: 'plan-1', shareToken: 'share-abc' }
const withParticipant: DeviceSession = {
  planId: 'plan-1',
  shareToken: 'share-abc',
  participant: { participantId: 'p1', participantToken: 'ptok', displayName: 'Ana' },
}

describe('plan session storage', () => {
  it('round-trips a session without a participant', () => {
    saveSession(base)
    expect(loadSession()).toEqual(base)
  })

  it('round-trips a session with a participant', () => {
    saveSession(withParticipant)
    expect(loadSession()).toEqual(withParticipant)
  })

  it('returns null when nothing is stored', () => {
    expect(loadSession()).toBeNull()
  })

  it('returns null for corrupted JSON', () => {
    sessionStorage.setItem('common-thread.plan-session.v1', '{bad json')
    expect(loadSession()).toBeNull()
  })

  it('rejects a structurally invalid session (missing shareToken)', () => {
    sessionStorage.setItem('common-thread.plan-session.v1', JSON.stringify({ planId: 'x' }))
    expect(loadSession()).toBeNull()
  })

  it('rejects a session with a malformed participant', () => {
    sessionStorage.setItem('common-thread.plan-session.v1',
      JSON.stringify({ planId: 'x', shareToken: 'y', participant: { participantId: 'p' } }))
    expect(loadSession()).toBeNull()
  })

  it('clears a stored session', () => {
    saveSession(base)
    clearSession()
    expect(loadSession()).toBeNull()
  })

  it('does not throw when storage is unavailable', () => {
    ;(globalThis as unknown as { sessionStorage: undefined }).sessionStorage = undefined as never
    expect(() => saveSession(base)).not.toThrow()
    expect(loadSession()).toBeNull()
  })
})
