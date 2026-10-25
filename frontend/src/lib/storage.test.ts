import { beforeEach, describe, expect, it } from 'vitest'
import { clearPlan, loadPlan, newPlanRef, savePlan, type SavedPlan } from './storage'

// Minimal in-memory localStorage so these pure helpers can be tested without jsdom.
class MemoryStorage {
  private store = new Map<string, string>()
  getItem(k: string) { return this.store.has(k) ? this.store.get(k)! : null }
  setItem(k: string, v: string) { this.store.set(k, v) }
  removeItem(k: string) { this.store.delete(k) }
  clear() { this.store.clear() }
}

beforeEach(() => {
  ;(globalThis as unknown as { localStorage: MemoryStorage }).localStorage = new MemoryStorage()
})

function samplePlan(): SavedPlan {
  return {
    planRef: newPlanRef(),
    savedAt: new Date().toISOString(),
    location: 'Austin',
    budget: '800',
    participants: [{ participant_id: 'p1', display_name: 'Ana', interestsText: 'jazz' }],
    result: null,
  }
}

describe('plan persistence', () => {
  it('round-trips a saved plan', () => {
    const plan = samplePlan()
    savePlan(plan)
    expect(loadPlan()).toEqual(plan)
  })

  it('returns null when nothing is saved', () => {
    expect(loadPlan()).toBeNull()
  })

  it('returns null for corrupted JSON rather than throwing', () => {
    localStorage.setItem('common-thread.lastPlan.v1', '{not valid json')
    expect(loadPlan()).toBeNull()
  })

  it('rejects a structurally invalid payload', () => {
    localStorage.setItem('common-thread.lastPlan.v1', JSON.stringify({ planRef: 'x', participants: 'nope' }))
    expect(loadPlan()).toBeNull()
  })

  it('clears a saved plan', () => {
    savePlan(samplePlan())
    clearPlan()
    expect(loadPlan()).toBeNull()
  })

  it('does not throw when storage is unavailable', () => {
    ;(globalThis as unknown as { localStorage: undefined }).localStorage = undefined as never
    expect(() => savePlan(samplePlan())).not.toThrow()
    expect(loadPlan()).toBeNull()
  })
})
